# -*- coding: utf-8 -*-
"""
Created on Sun May 12 20:46:26 2019

@author: syuntoku
"""

import adsk, copy, os, re
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, SubElement
from . import Link, Joint, launch_templates
from ..utils import utils

def write_link_urdf(joints_dict, repo, links_xyz_dict, file_name, inertial_dict):
    """
    Write links information into urdf "repo/file_name"


    Parameters
    ----------
    joints_dict: dict
        information of the each joint
    repo: str
        the name of the repository to save the xml file
    links_xyz_dict: vacant dict
        xyz information of the each link
    file_name: str
        urdf full path
    inertial_dict:
        information of the each inertial

    Note
    ----------
    In this function, links_xyz_dict is set for write_joint_tran_urdf.
    The origin of the coordinate of center_of_mass is the coordinate of the link
    """
    with open(file_name, mode='a') as f:
        # for base_link
        center_of_mass = inertial_dict['base_link']['center_of_mass']
        link = Link.Link(name='base_link', xyz=[0,0,0],
            center_of_mass=center_of_mass, repo=repo,
            mass=inertial_dict['base_link']['mass'],
            inertia_tensor=inertial_dict['base_link']['inertia'])
        links_xyz_dict[link.name] = link.xyz
        link.make_link_xml()
        f.write(link.link_xml)
        f.write('\n')

        # others
        for joint in joints_dict:
            name = joints_dict[joint]['child']
            center_of_mass = \
                [ i-j for i, j in zip(inertial_dict[name]['center_of_mass'], joints_dict[joint]['xyz'])]
            link = Link.Link(name=name, xyz=joints_dict[joint]['xyz'],\
                center_of_mass=center_of_mass,\
                repo=repo, mass=inertial_dict[name]['mass'],\
                inertia_tensor=inertial_dict[name]['inertia'])
            links_xyz_dict[link.name] = link.xyz
            link.make_link_xml()
            f.write(link.link_xml)
            f.write('\n')


def write_joint_urdf(joints_dict, repo, links_xyz_dict, file_name):
    """
    Write joints and transmission information into urdf "repo/file_name"


    Parameters
    ----------
    joints_dict: dict
        information of the each joint
    repo: str
        the name of the repository to save the xml file
    links_xyz_dict: dict
        xyz information of the each link
    file_name: str
        urdf full path
    """

    with open(file_name, mode='a') as f:
        for j in joints_dict:
            parent = joints_dict[j]['parent']
            child = joints_dict[j]['child']
            joint_type = joints_dict[j]['type']
            upper_limit = joints_dict[j]['upper_limit']
            lower_limit = joints_dict[j]['lower_limit']
            try:
                xyz = [round(p-c, 6) for p, c in \
                    zip(links_xyz_dict[parent], links_xyz_dict[child])]  # xyz = parent - child
            except KeyError as ke:
                app = adsk.core.Application.get()
                ui = app.userInterface
                ui.messageBox("There seems to be an error with the connection between\n\n%s\nand\n%s\n\nCheck \
whether the connections\nparent=component2=%s\nchild=component1=%s\nare correct or if you need \
to swap component1<=>component2"
                % (parent, child, parent, child), "Error!")
                quit()

            joint = Joint.Joint(name=j, joint_type = joint_type, xyz=xyz, \
            axis=joints_dict[j]['axis'], parent=parent, child=child, \
            upper_limit=upper_limit, lower_limit=lower_limit)
            joint.make_joint_xml()
            joint.make_transmission_xml()
            f.write(joint.joint_xml)
            f.write('\n')

def write_gazebo_endtag(file_name):
    """
    Write about gazebo_plugin and the </robot> tag at the end of the urdf


    Parameters
    ----------
    file_name: str
        urdf full path
    """
    with open(file_name, mode='a') as f:
        f.write('</robot>\n')


def write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir):
    try: os.mkdir(save_dir + '/urdf')
    except: pass

    file_name = save_dir + '/urdf/' + robot_name + '.xacro'  # the name of urdf file
    repo = package_name + '/meshes/'  # the repository of binary stl files
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro">\n'.format(robot_name))
        f.write('\n')
        f.write('<xacro:include filename="$(find {})/urdf/materials.xacro" />'.format(package_name))
        f.write('\n')
        f.write('<xacro:include filename="$(find {})/urdf/{}.trans" />'.format(package_name, robot_name))
        f.write('\n')
        f.write('<xacro:include filename="$(find {})/urdf/{}.gazebo" />'.format(package_name, robot_name))
        f.write('\n')

    write_link_urdf(joints_dict, repo, links_xyz_dict, file_name, inertial_dict)
    write_joint_urdf(joints_dict, repo, links_xyz_dict, file_name)
    write_gazebo_endtag(file_name)

def write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir):
    try: os.mkdir(save_dir + '/urdf')
    except: pass

    file_name = save_dir + '/urdf/materials.xacro'  # the name of urdf file
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro" >\n'.format(robot_name))
        f.write('\n')
        f.write('<material name="silver">\n')
        f.write('  <color rgba="0.700 0.700 0.700 1.000"/>\n')
        f.write('</material>\n')
        f.write('\n')
        f.write('</robot>\n')

def write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir):
    """
    Write joints and transmission information into urdf "repo/file_name"


    Parameters
    ----------
    joints_dict: dict
        information of the each joint
    repo: str
        the name of the repository to save the xml file
    links_xyz_dict: dict
        xyz information of the each link
    file_name: str
        urdf full path
    """

    file_name = save_dir + '/urdf/{}.trans'.format(robot_name)  # the name of urdf file
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro" >\n'.format(robot_name))
        f.write('\n')

        for j in joints_dict:
            parent = joints_dict[j]['parent']
            child = joints_dict[j]['child']
            joint_type = joints_dict[j]['type']
            upper_limit = joints_dict[j]['upper_limit']
            lower_limit = joints_dict[j]['lower_limit']
            try:
                xyz = [round(p-c, 6) for p, c in \
                    zip(links_xyz_dict[parent], links_xyz_dict[child])]  # xyz = parent - child
            except KeyError as ke:
                app = adsk.core.Application.get()
                ui = app.userInterface
                ui.messageBox("There seems to be an error with the connection between\n\n%s\nand\n%s\n\nCheck \
whether the connections\nparent=component2=%s\nchild=component1=%s\nare correct or if you need \
to swap component1<=>component2"
                % (parent, child, parent, child), "Error!")
                quit()

            joint = Joint.Joint(name=j, joint_type = joint_type, xyz=xyz, \
            axis=joints_dict[j]['axis'], parent=parent, child=child, \
            upper_limit=upper_limit, lower_limit=lower_limit)
            if joint_type != 'fixed':
                joint.make_transmission_xml()
                f.write(joint.tran_xml)
                f.write('\n')

        f.write('</robot>\n')

def write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir):
    try: os.mkdir(save_dir + '/urdf')
    except: pass

    file_name = save_dir + '/urdf/' + robot_name + '.gazebo'  # the name of urdf file
    repo = robot_name + '/meshes/'  # the repository of binary stl files
    #repo = package_name + '/' + robot_name + '/bin_stl/'  # the repository of binary stl files
    with open(file_name, mode='w') as f:
        f.write('<?xml version="1.0" ?>\n')
        f.write('<robot name="{}" xmlns:xacro="http://www.ros.org/wiki/xacro" >\n'.format(robot_name))
        f.write('\n')
        f.write('<xacro:property name="body_color" value="Gazebo/Silver" />\n')
        f.write('\n')

        gazebo = Element('gazebo')
        plugin = SubElement(gazebo, 'plugin')
        plugin.attrib = {'name':'control', 'filename':'libgazebo_ros_control.so'}
        gazebo_xml = "\n".join(utils.prettify(gazebo).split("\n")[1:])
        f.write(gazebo_xml)

        # for base_link
        f.write('<gazebo reference="base_link">\n')
        f.write('  <material>${body_color}</material>\n')
        f.write('  <mu1>0.2</mu1>\n')
        f.write('  <mu2>0.2</mu2>\n')
        f.write('  <self_collide>true</self_collide>\n')
        f.write('  <gravity>true</gravity>\n')
        f.write('</gazebo>\n')
        f.write('\n')

        # others
        for joint in joints_dict:
            name = joints_dict[joint]['child']
            f.write('<gazebo reference="{}">\n'.format(name))
            f.write('  <material>${body_color}</material>\n')
            f.write('  <mu1>0.2</mu1>\n')
            f.write('  <mu2>0.2</mu2>\n')
            f.write('  <self_collide>true</self_collide>\n')
            f.write('</gazebo>\n')
            f.write('\n')

        f.write('</robot>\n')


XACRO_NAMESPACE = 'http://www.ros.org/wiki/xacro'


def _xacro_name(element):
    prefix = '{' + XACRO_NAMESPACE + '}'
    if element.tag.startswith(prefix):
        return element.tag[len(prefix):]
    return None


def _read_robot_fragment(file_name):
    root = ElementTree.parse(file_name).getroot()
    if root.tag != 'robot':
        raise ValueError('{} does not contain a <robot> root'.format(file_name))
    return root


def _collect_xacro_properties(roots):
    properties = {}
    for root in roots:
        for child in root:
            if _xacro_name(child) != 'property':
                continue
            name = child.attrib.get('name')
            value = child.attrib.get('value')
            if not name or value is None:
                raise ValueError('xacro property is missing name or value')
            properties[name] = value
    return properties


def _append_plain_children(target, source, allowed_xacro_elements):
    for child in source:
        xacro_name = _xacro_name(child)
        if xacro_name is not None:
            if xacro_name not in allowed_xacro_elements:
                raise ValueError(
                    'unsupported xacro element <xacro:{}> in generated export'
                    .format(xacro_name)
                )
            continue
        target.append(copy.deepcopy(child))


def _expand_xacro_properties(root, properties):
    def expand(value):
        if value is None:
            return None
        for name, replacement in properties.items():
            value = value.replace('${' + name + '}', replacement)
        return value

    for element in root.iter():
        element.text = expand(element.text)
        element.tail = expand(element.tail)
        for name, value in list(element.attrib.items()):
            element.attrib[name] = expand(value)


def _normalise_mesh_uris(root):
    find_pattern = re.compile(r'^(?:file://)?\$\(find ([^)]+)\)/?(.*)$')
    for mesh in root.iter('mesh'):
        filename = mesh.attrib.get('filename')
        if not filename:
            continue
        match = find_pattern.match(filename)
        if match:
            package, path = match.groups()
            mesh.attrib['filename'] = 'package://{}/{}'.format(
                package, path.lstrip('/')
            )


def _validate_plain_urdf(root):
    links = [link.attrib.get('name') for link in root.findall('link')]
    if not links or any(not name for name in links):
        raise ValueError('plain URDF contains an unnamed link or no links')
    if len(links) != len(set(links)):
        raise ValueError('plain URDF contains duplicate link names')

    link_names = set(links)
    missing_links = set()
    for joint in root.findall('joint'):
        parent = joint.find('parent')
        child = joint.find('child')
        if parent is None or child is None:
            raise ValueError(
                "joint '{}' is missing a parent or child"
                .format(joint.attrib.get('name', '?'))
            )
        for link_name in (parent.attrib.get('link'), child.attrib.get('link')):
            if link_name not in link_names:
                missing_links.add(link_name)
    if missing_links:
        raise ValueError(
            'plain URDF references missing links: {}'
            .format(', '.join(sorted(missing_links)))
        )

    for element in root.iter():
        if _xacro_name(element) is not None:
            raise ValueError('plain URDF still contains a xacro element')
        values = [element.text, element.tail] + list(element.attrib.values())
        for value in values:
            if value and ('${' in value or '$(find ' in value):
                raise ValueError(
                    'plain URDF still contains an unresolved xacro expression: {}'
                    .format(value)
                )


def write_plain_urdf(package_name, robot_name, save_dir):
    """Bundle the generated xacro fragments into a standalone ROS URDF."""
    urdf_dir = os.path.join(save_dir, 'urdf')
    xacro_root = _read_robot_fragment(
        os.path.join(urdf_dir, robot_name + '.xacro')
    )
    materials_root = _read_robot_fragment(
        os.path.join(urdf_dir, 'materials.xacro')
    )
    transmissions_root = _read_robot_fragment(
        os.path.join(urdf_dir, robot_name + '.trans')
    )
    gazebo_root = _read_robot_fragment(
        os.path.join(urdf_dir, robot_name + '.gazebo')
    )
    fragment_roots = [
        xacro_root, materials_root, transmissions_root, gazebo_root
    ]

    properties = _collect_xacro_properties(fragment_roots)
    bundled_root = Element('robot', {'name': robot_name})
    _append_plain_children(bundled_root, materials_root, {'property'})
    _append_plain_children(bundled_root, xacro_root, {'include'})
    _append_plain_children(bundled_root, transmissions_root, {'property'})
    _append_plain_children(bundled_root, gazebo_root, {'property'})
    _expand_xacro_properties(bundled_root, properties)
    _normalise_mesh_uris(bundled_root)
    _validate_plain_urdf(bundled_root)

    file_name = os.path.join(urdf_dir, robot_name + '.urdf')
    temporary_file = file_name + '.tmp'
    try:
        with open(temporary_file, mode='w', encoding='utf-8') as f:
            f.write(utils.prettify(bundled_root))
        written_root = ElementTree.parse(temporary_file).getroot()
        _validate_plain_urdf(written_root)
        os.replace(temporary_file, file_name)
    finally:
        if os.path.exists(temporary_file):
            os.remove(temporary_file)

    return file_name

def write_display_launch(package_name, robot_name, save_dir):
    """
    write display launch file "save_dir/launch/display.launch"


    Parameter
    ---------
    robot_name: str
    name of the robot
    save_dir: str
    path of the repository to save
    """
    try: os.mkdir(save_dir + '/launch')
    except: pass

    file_text = launch_templates.get_display_launch_text(package_name, robot_name)

    file_name = os.path.join(save_dir, 'launch', 'display.launch.py')
    with open(file_name, mode='w') as f:
        f.write(file_text)

def write_gazebo_launch(package_name, robot_name, save_dir):
    """
    write gazebo launch file "save_dir/launch/gazebo.launch"


    Parameter
    ---------
    robot_name: str
        name of the robot
    save_dir: str
        path of the repository to save
    """

    try: os.mkdir(save_dir + '/launch')
    except: pass

    file_text = launch_templates.get_gazebo_launch_text(package_name, robot_name)

    file_name = os.path.join(save_dir, 'launch', 'gazebo.launch.py')
    with open(file_name, mode='w') as f:
        f.write(file_text)
