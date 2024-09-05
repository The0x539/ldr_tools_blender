from typing import Callable
import os.path

from .ldr_tools_py import LDrawColor
from .colors import rgb_peeron_by_code, rgb_ldr_tools_by_code
from . import node_dsl

import bpy

# Materials are based on the techniques described in the following blog posts.
# This covers how to create lego shaders with realistic surface detailing.
# https://stefanmuller.com/exploring-lego-material-part-1/
# https://stefanmuller.com/exploring-lego-material-part-2/
# https://stefanmuller.com/exploring-lego-material-part-3/


def get_material(
    color_by_code: dict[int, LDrawColor], code: int, is_slope: bool
) -> bpy.types.Material:
    # Cache materials by name.
    # This loads materials lazily to avoid creating unused colors.
    ldraw_color = color_by_code.get(code)

    name = str(code)
    if ldraw_color is not None:
        name = f"{code} {ldraw_color.name}"
        if is_slope:
            name += " slope"

    # Skip as much work as possible if the material already exists.
    if material := bpy.data.materials.get(name):
        return material

    current_dir = os.path.dirname(__file__)
    material_dir = os.path.join(current_dir, "nodes")

    # Eagerly load the node groups because there are only a handful.
    for group_name in ("normal", "slope_normal", "is_slope", "roughness", "speckle"):
        prefixed_group_name = "ldr_tools_" + group_name
        if prefixed_group_name not in bpy.data.node_groups:
            group_filepath = os.path.join(material_dir, group_name + ".group.yml")
            node_dsl.load_shader_node_group(group_filepath, prefixed_group_name)

    # TODO: Report warnings if a part contains an invalid color code.

    material_filepath = os.path.join(material_dir, "base.material.yml")
    material = node_dsl.load_material(material_filepath, name)

    nodes = material.node_tree.nodes

    if ldraw_color is None:
        # TODO: Error if color is missing?
        return material

    r, g, b, a = ldraw_color.rgba_linear

    # Set the color in the viewport.
    # This can use the default LDraw color for familiarity.
    material.diffuse_color = (r, g, b, a)

    # Partially complete alternatives to LDraw colors for better realism.
    if code in rgb_ldr_tools_by_code:
        r, g, b = rgb_ldr_tools_by_code[code]
    elif code in rgb_peeron_by_code:
        r, g, b = rgb_peeron_by_code[code]

    # Alpha is specified using transmission instead.
    nodes["base_color"].outputs[0].default_value = (r, g, b, 1.0)

    bsdf = nodes["bsdf"]
    bsdf.inputs["Subsurface Radius"].default_value = (r, g, b)

    metal = 0.0
    rough = (0.075, 0.2)

    match ldraw_color.finish_name:
        case "MatteMetallic":
            metal = 1.0
        case "Chrome":
            # Glossy metal coating.
            metal = 1.0
            rough = (0.075, 0.1)
        case "Metal":
            # Rougher metals.
            metal = 1.0
            rough = (0.15, 0.3)
        case "Pearlescent":
            metal = 0.35
            rough = (0.3, 0.5)
        case "Speckle":
            # TODO: Are all speckled colors metals?
            metal = 1.0

            speckle_node = nodes["speckle"]
            speckle_node.mute = False
            sp_r, sp_g, sp_b, _ = ldraw_color.speckle_rgba_linear
            speckle_node.inputs["Speckle Color"].default_value = (sp_r, sp_g, sp_b, 1.0)

    bsdf.inputs["Metallic"].default_value = metal

    # Transparent colors specify an alpha of 128 / 255.
    if a <= 0.6:
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["IOR"].default_value = 1.55

        if ldraw_color.finish_name == "Rubber":
            # Make the transparent rubber appear cloudy.
            rough = (0.1, 0.35)
        else:
            rough = (0.01, 0.15)

    nodes["roughness"].inputs["Min"].default_value = rough[0]
    nodes["roughness"].inputs["Max"].default_value = rough[1]

    if is_slope:
        nodes["mix_normals"].mute = False

    return material
