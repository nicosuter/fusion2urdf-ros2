#Author-syuntoku14
#Description-Generate URDF file from Fusion 360

import adsk, adsk.core, adsk.fusion, traceback
import os
import sys
from .utils import utils
from .core import Link, Joint, Write


def _cad_signature(root):
    occurrences = tuple(
        (occurrence.fullPathName, occurrence.component.name,
         occurrence.bRepBodies.count,
         tuple(occurrence.transform2.asArray()),
         occurrence.isGrounded)
        for occurrence in root.occurrences
    )
    joints = tuple(
        (joint.name,
         joint.occurrenceOne.fullPathName if joint.occurrenceOne else None,
         joint.occurrenceTwo.fullPathName if joint.occurrenceTwo else None)
        for joint in root.joints
    )
    return occurrences, joints, root.bRepBodies.count

"""
# length unit is 'cm' and inertial unit is 'kg/cm^2'
# If there is no 'body' in the root component, maybe the corrdinates are wrong.
"""

# joint effort: 100
# joint velocity: 100
# supports "Revolute", "Rigid" and "Slider" joint types

# I'm not sure how prismatic joint acts if there is no limit in fusion model

def run(context):
    ui = None
    root = None
    before_signature = None
    success_msg = 'Successfully create URDF file'
    msg = success_msg

    try:
        # --------------------
        # initialize
        app = adsk.core.Application.get()
        ui = app.userInterface
        product = app.activeProduct
        design = adsk.fusion.Design.cast(product)
        title = 'Fusion2URDF'
        if not design:
            ui.messageBox('No active Fusion design', title)
            return

        root = design.rootComponent  # root component
        before_signature = _cad_signature(root)

        # set the names
        robot_name = root.name.split()[0]
        package_name = robot_name + '_description'
        save_dir = utils.file_dialog(ui)
        if save_dir == False:
            ui.messageBox('Fusion2URDF was canceled', title)
            return 0

        save_dir = save_dir + '/' + package_name
        try: os.mkdir(save_dir)
        except: pass

        package_dir = os.path.abspath(os.path.dirname(__file__)) + '/package/'

        # --------------------
        # set dictionaries

        # Generate joints_dict. All joints are related to root.
        joints_dict, msg = Joint.make_joints_dict(root, msg)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return 0

        # Generate inertial_dict
        inertial_dict, msg = Link.make_inertial_dict(root, msg)
        if msg != success_msg:
            ui.messageBox(msg, title)
            return 0
        elif not 'base_link' in inertial_dict:
            msg = 'There is no base_link. Please set base_link and run again.'
            ui.messageBox(msg, title)
            return 0

        links_xyz_dict = {}

        # --------------------
        # Generate URDF
        Write.write_urdf(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_materials_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_transmissions_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_gazebo_xacro(joints_dict, links_xyz_dict, inertial_dict, package_name, robot_name, save_dir)
        Write.write_display_launch(package_name, robot_name, save_dir)
        Write.write_gazebo_launch(package_name, robot_name, save_dir)

        # copy over package files
        utils.create_package(package_name, save_dir, package_dir)
        utils.update_setup_py(save_dir, package_name)
        utils.update_setup_cfg(save_dir, package_name)
        utils.update_package_xml(save_dir, package_name)

        # Export the original occurrences directly. This must not clone, rename,
        # delete, or otherwise mutate anything in the CAD document.
        exported_meshes = utils.export_stl(design, root, save_dir)
        Write.write_plain_urdf(
            package_name, robot_name, save_dir, exported_meshes
        )

        after_signature = _cad_signature(root)
        if after_signature != before_signature:
            raise RuntimeError(
                'Exporter changed CAD names, joint endpoints, body counts, '
                'occurrence transforms, grounding, or root bodies; output rejected'
            )

        ui.messageBox(msg, title)

    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
    finally:
        if root is not None and before_signature is not None:
            try:
                if _cad_signature(root) != before_signature and ui:
                    ui.messageBox(
                        'CRITICAL: exporter source-state guard detected a CAD '
                        'document change. Do not save this document.'
                    )
            except Exception:
                if ui:
                    ui.messageBox(
                        'CRITICAL: exporter could not verify the final CAD state. '
                        'Do not save this document.'
                    )
