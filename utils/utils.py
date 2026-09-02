# -*- coding: utf-8 -*-
"""
Created on Sun May 12 19:15:34 2019

@author: syuntoku
"""

import adsk, adsk.core, adsk.fusion
import os.path, re
import shutil
import struct
import tempfile
from xml.etree import ElementTree
from xml.dom import minidom
from shutil import copytree
import fileinput
import math
import sys

def _mesh_name(occurrence):
    if occurrence.component.name == 'base_link':
        return 'base_link.stl'
    return re.sub('[ :()]', '_', occurrence.name) + '.stl'


def _validate_binary_stl(path):
    size = os.path.getsize(path)
    if size < 84:
        raise ValueError('{} is shorter than a binary STL header'.format(path))
    with open(path, 'rb') as stl:
        stl.seek(80)
        triangle_count = struct.unpack('<I', stl.read(4))[0]
    if triangle_count == 0:
        raise ValueError('{} contains no triangles'.format(path))
    expected_size = 84 + 50 * triangle_count
    if size != expected_size:
        raise ValueError(
            '{} has size {}, expected {} for {} triangles'
            .format(path, size, expected_size, triangle_count)
        )


def _write_binary_stl(body, path):
    """Write a transient Fusion BRep as millimetre binary STL."""
    calculator = body.meshManager.createMeshCalculator()
    if calculator is None:
        raise RuntimeError('Fusion could not create a mesh calculator')
    if not calculator.setQuality(
            adsk.fusion.TriangleMeshQualityOptions.NormalQualityTriangleMesh):
        raise RuntimeError('Fusion rejected normal-quality mesh settings')
    mesh = calculator.calculate()
    if mesh is None:
        raise RuntimeError('Fusion could not calculate a triangle mesh')

    # Fusion API geometry is in centimetres; STL files in this package are in
    # millimetres and the URDF intentionally applies a 0.001 mesh scale.
    coordinates = [value * 10.0 for value in mesh.nodeCoordinatesAsDouble]
    indices = mesh.nodeIndices
    if len(indices) != mesh.triangleCount * 3:
        raise RuntimeError('Fusion returned an inconsistent triangle index list')

    with open(path, 'wb') as stl:
        stl.write(b'Fusion transient world-frame export'.ljust(80, b'\0'))
        stl.write(struct.pack('<I', mesh.triangleCount))
        for triangle in range(mesh.triangleCount):
            offset = triangle * 3
            i0, i1, i2 = indices[offset:offset + 3]
            p0 = coordinates[i0 * 3:i0 * 3 + 3]
            p1 = coordinates[i1 * 3:i1 * 3 + 3]
            p2 = coordinates[i2 * 3:i2 * 3 + 3]
            ux, uy, uz = (p1[i] - p0[i] for i in range(3))
            vx, vy, vz = (p2[i] - p0[i] for i in range(3))
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length:
                nx, ny, nz = nx / length, ny / length, nz / length
            stl.write(struct.pack(
                '<12fH', nx, ny, nz,
                p0[0], p0[1], p0[2],
                p1[0], p1[1], p1[2],
                p2[0], p2[1], p2[2], 0
            ))


def export_stl(design, root, save_dir):
    """
    export stl files into "sace_dir/"


    Parameters
    ----------
    design: adsk.fusion.Design.cast(product)
    save_dir: str
        directory path to save
    root: design.rootComponent

    Returns the exact basenames exported by this run. Occurrences are exported
    directly, exactly as Fusion emits them. No vertex, origin, or occurrence
    transform is rewritten. This also avoids the old implementation's permanent
    ``old_component`` renames.
    """
    temporary_brep = adsk.fusion.TemporaryBRepManager.get()
    mesh_dir = os.path.join(save_dir, 'meshes')
    os.makedirs(mesh_dir, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix='.fusion2urdf-', dir=mesh_dir)
    staged = []
    names = set()
    try:
        for occurrence in root.occurrences:
            name = _mesh_name(occurrence)
            if name in names:
                raise ValueError('two occurrences export to the same mesh: ' + name)
            if occurrence.bRepBodies.count != 1:
                raise ValueError(
                    "occurrence '{}' has {} bodies; expected exactly one for {}"
                    .format(occurrence.fullPathName, occurrence.bRepBodies.count, name)
                )
            names.add(name)
            temporary_path = os.path.join(temp_dir, name)
            # Copy the native body into Fusion's in-memory BRep manager and ask
            # Fusion to apply the occurrence's existing assembly transform to
            # that transient copy. No component, body, transform, vertex, or
            # joint in the source design is written.
            native_body = occurrence.bRepBodies.item(0).nativeObject
            export_body = temporary_brep.copy(native_body)
            if export_body is None:
                raise RuntimeError(
                    "Fusion could not copy native body for {}"
                    .format(occurrence.fullPathName)
                )
            if not export_body.isTemporary:
                raise RuntimeError('Refusing to transform a document-owned body')
            if not temporary_brep.transform(export_body, occurrence.transform2):
                raise RuntimeError(
                    "Fusion could not apply assembly context for {}"
                    .format(occurrence.fullPathName)
                )
            _write_binary_stl(export_body, temporary_path)
            _validate_binary_stl(temporary_path)
            staged.append((temporary_path, os.path.join(mesh_dir, name)))

        for temporary_path, final_path in staged:
            os.replace(temporary_path, final_path)
        print('[mesh] exported and validated {} binary STL files'.format(len(names)), flush=True)
        return names
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def file_dialog(ui):
    """
    display the dialog to save the file
    """
    # Set styles of folder dialog.
    folderDlg = ui.createFolderDialog()
    folderDlg.title = 'Fusion Folder Dialog'

    # Show folder dialog
    dlgResult = folderDlg.showDialog()
    if dlgResult == adsk.core.DialogResults.DialogOK:
        return folderDlg.folder
    return False


def round_significant(value, digits=9):
    """Round inertia values without erasing small links' significant digits."""
    if value == 0.0 or not math.isfinite(value):
        return value
    return round(value, digits - 1 - int(math.floor(math.log10(abs(value)))))


def origin2center_of_mass(inertia, center_of_mass, mass):
    """
    convert the moment of the inertia about the world coordinate into
    that about center of mass coordinate


    Parameters
    ----------
    moment of inertia about the world coordinate:  [xx, yy, zz, xy, yz, xz]
    center_of_mass: [x, y, z]


    Returns
    ----------
    moment of inertia about center of mass : [xx, yy, zz, xy, yz, xz]
    """
    x = center_of_mass[0]
    y = center_of_mass[1]
    z = center_of_mass[2]
    translation_matrix = [y**2+z**2, x**2+z**2, x**2+y**2,
                         -x*y, -y*z, -x*z]
    return [round_significant(i - mass*t)
            for i, t in zip(inertia, translation_matrix)]


def prettify(elem):
    """
    Return a pretty-printed XML string for the Element.
    Parameters
    ----------
    elem : xml.etree.ElementTree.Element


    Returns
    ----------
    pretified xml : str
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def create_package(package_name, save_dir, package_dir):
    try: os.mkdir(save_dir + '/launch')
    except: pass

    try: os.mkdir(save_dir + '/urdf')
    except: pass

    try: os.mkdir(save_dir + '/config')
    except: pass

    try: os.mkdir(save_dir + '/' +package_name)
    except: pass
    with open(os.path.join(save_dir, package_name, '__init__.py'), 'w'):
        pass

    try: os.mkdir(save_dir + '/resource')
    except: pass
    with open(os.path.join(save_dir, 'resource', package_name), 'w'):
        pass

    try: os.mkdir(save_dir + '/test')
    except: pass

    copytree(package_dir, save_dir, dirs_exist_ok=True)

def update_setup_py(save_dir, package_name):
    file_name = save_dir + '/setup.py'

    for line in fileinput.input(file_name, inplace=True):
        if "package_name = 'fusion2urdf_ros2'" in line:
            sys.stdout.write("package_name = '" + package_name + "'\n")
        else:
            sys.stdout.write(line)

def update_setup_cfg(save_dir, package_name):
    file_name = save_dir + '/setup.cfg'

    for line in fileinput.input(file_name, inplace=True):
        if "script_dir" in line:
            sys.stdout.write("script_dir=$base/lib/" + package_name + "\n")
        elif "install_scripts" in line:
            sys.stdout.write("install_scripts=$base/lib/" + package_name + "\n")
        else:
            sys.stdout.write(line)

def update_package_xml(save_dir, package_name):
    file_name = save_dir + '/package.xml'

    for line in fileinput.input(file_name, inplace=True):
        if '<name>' in line:
            sys.stdout.write("<name>" + package_name + "</name>\n")
        elif '<description>' in line:
            sys.stdout.write("<description>The " + package_name + " package</description>\n")
        else:
            sys.stdout.write(line)
