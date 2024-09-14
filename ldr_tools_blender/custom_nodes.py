import bpy
from .node_dsl import NodeGraph

from bpy.types import (
    NodeSocketInt,
    NodeSocketFloat,
    NodeSocketColor,
    NodeSocketBool,
    NodeSocketVector,
    NodeGroupInput,
    NodeGroupOutput,
    ShaderNodeObjectInfo,
    ShaderNodeTree,
    ShaderNodeMath,
    NodeTreeInterfaceSocketInt,
    ShaderNodeMapRange,
    ShaderNodeMix,
    ShaderNodeTexCoord,
    ShaderNodeSeparateXYZ,
    ShaderNodeCombineXYZ,
)


def node_group_uv_degradation() -> ShaderNodeTree:
    if tree := bpy.data.node_groups.get("UV Degradation"):
        assert isinstance(tree, ShaderNodeTree)
        return tree

    tree = bpy.data.node_groups.new("UV Degradation", "ShaderNodeTree")  # type: ignore
    assert isinstance(tree, ShaderNodeTree)
    graph = NodeGraph(tree)

    graph.input(NodeSocketColor, "FromColor")
    graph.input(NodeSocketColor, "ToColor")
    graph.input(NodeSocketFloat, "MinColorRatio")
    graph.input(NodeSocketFloat, "MaxColorRatio")
    graph.input(NodeSocketFloat, "MinRoughness")
    graph.input(NodeSocketFloat, "MaxRoughness")
    graph.input(NodeSocketFloat, "Strength")
    graph.input(NodeSocketBool, "enable")
    graph.input(NodeSocketInt, "Levels")

    graph.output(NodeSocketColor, "OutColor")
    graph.output(NodeSocketFloat, "OutRoughness")

    levels_socket: NodeTreeInterfaceSocketInt = tree.interface.items_tree[
        "Levels"
    ]  # type:ignore
    levels_socket.min_value = 1
    levels_socket.default_value = 4
    levels_socket.max_value = 10

    input = graph.node(NodeGroupInput)
    object_info = graph.node(ShaderNodeObjectInfo)

    step_1 = graph.node(
        ShaderNodeMath,
        operation="MULTIPLY",
        inputs=[object_info["Random"], input["Levels"]],
    )

    step_2 = graph.node(ShaderNodeMath, operation="FLOOR", inputs=[step_1])

    step_3 = graph.node(
        ShaderNodeMath, operation="SUBTRACT", inputs=[input["Levels"], 1.0]
    )

    t = graph.node(
        ShaderNodeMath,
        operation="DIVIDE",
        use_clamp=True,
        inputs=[step_2, step_3],
        label="t",
    )

    input2 = graph.node(NodeGroupInput, label="Group Input (Strength)")

    color_ratio = graph.node(
        ShaderNodeMapRange,
        label="ColorRatio",
        inputs={
            "Value": t,
            "To Min": input2["MinColorRatio"],
            "To Max": input2["MaxColorRatio"],
        },
    )

    color_t = graph.node(
        ShaderNodeMath,
        operation="MULTIPLY",
        label="color_t",
        inputs=[color_ratio, input2["Strength"]],
    )

    t_strength = graph.node(
        ShaderNodeMath,
        operation="MULTIPLY",
        label="t * Strength",
        inputs=[t, input2["Strength"]],
    )

    input3 = graph.node(NodeGroupInput, label="Group Input (Ranges)")

    out_color = graph.node(
        ShaderNodeMix,
        label="OutColor",
        inputs={0: color_t, "A": input3["FromColor"], "B": input3["ToColor"]},
    )

    out_roughness = graph.node(
        ShaderNodeMapRange,
        label="OutRoughness",
        clamp=False,
        inputs={
            "Value": t_strength,
            "To Min": input3["MinRoughness"],
            "To Max": input3["MaxRoughness"],
        },
    )

    input4 = graph.node(NodeGroupInput, label="Group Input (Toggles)")

    toggle_out_color = graph.node(
        ShaderNodeMix,
        label="Color Toggle",
        data_type="RGBA",
        inputs={0: input4["enable"], "A": input4["FromColor"], "B": out_color},
    )

    toggle_out_roughness = graph.node(
        ShaderNodeMix,
        label="Roughness Toggle",
        data_type="FLOAT",
        inputs={0: input4["enable"], "A": input4["MinRoughness"], "B": out_roughness},
    )

    graph.node(
        NodeGroupOutput,
        inputs={
            "OutColor": toggle_out_color,
            "OutRoughness": toggle_out_roughness,
        },
    )

    return tree


def node_group_project_to_axis_plane() -> ShaderNodeTree:
    if tree := bpy.data.node_groups.get("Project To Axis Plane"):
        assert isinstance(tree, ShaderNodeTree)
        return tree

    tree = bpy.data.node_groups.new("Project To Axis Plane", "ShaderNodeTree")  # type: ignore
    assert isinstance(tree, ShaderNodeTree)
    graph = NodeGraph(tree)

    graph.input(NodeSocketVector, "In")
    graph.output(NodeSocketVector, "Out")

    input = graph.node(NodeGroupInput)

    tex_coord = graph.node(ShaderNodeTexCoord)

    split_normal = graph.node(
        ShaderNodeSeparateXYZ, label="Split Normal", inputs=[tex_coord["Normal"]]
    )

    abs_x = graph.node(
        ShaderNodeMath, operation="ABSOLUTE", label="Abs(X)", inputs=[split_normal["X"]]
    )
    abs_y = graph.node(
        ShaderNodeMath, operation="ABSOLUTE", label="Abs(Y)", inputs=[split_normal["Y"]]
    )

    facing_x = graph.node(
        ShaderNodeMath, operation="GREATER_THAN", label="Facing X", inputs=[abs_x, 0.5]
    )
    facing_y = graph.node(
        ShaderNodeMath, operation="GREATER_THAN", label="Facing Y", inputs=[abs_y, 0.5]
    )

    split_pos = graph.node(
        ShaderNodeSeparateXYZ, label="Split Position", inputs=[input]
    )

    xzy = graph.node(
        ShaderNodeCombineXYZ,
        label="XZY",
        inputs=[split_pos["X"], split_pos["Z"], split_pos["Y"]],
    )
    yzx = graph.node(
        ShaderNodeCombineXYZ,
        label="YZX",
        inputs=[split_pos["Y"], split_pos["Z"], split_pos["X"]],
    )

    elif_facing_x = graph.node(
        ShaderNodeMix,
        label="elseif facing X",
        data_type="VECTOR",
        inputs={"Factor": facing_x, "B": yzx, "A": input},
    )

    if_facing_y = graph.node(
        ShaderNodeMix,
        label="if facing Y",
        data_type="VECTOR",
        inputs={"Factor": facing_y, "B": xzy, "A": elif_facing_x},
    )

    graph.node(NodeGroupOutput, inputs=[if_facing_y])

    return tree
