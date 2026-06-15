bl_info = {
    "name": "Enfusion Texture Packer",
    "author": "OpenAI Codex",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Enfusion > Texture Packer",
    "description": "Pack material textures into Arma Reforger _BCR and _NMO channel formats.",
    "category": "Material",
}

import os
import re

import bpy


def clean_name(name):
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "Material"


def material_slots_from_selection(context):
    materials = []
    seen = set()
    for obj in context.selected_objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.name not in seen:
                seen.add(mat.name)
                materials.append(mat)
    return materials


def image_is_loaded(image):
    return image and image.size[0] > 0 and image.size[1] > 0


def lower_name(item):
    return item.name.lower() if item else ""


def image_candidates(material):
    if not material or not material.use_nodes:
        return []
    out = []
    for node in material.node_tree.nodes:
        if node.bl_idname == "ShaderNodeTexImage" and image_is_loaded(node.image):
            out.append((node, node.image, lower_name(node) + " " + lower_name(node.image)))
    return out


def find_principled(material):
    if not material or not material.use_nodes:
        return None
    for node in material.node_tree.nodes:
        if node.bl_idname == "ShaderNodeBsdfPrincipled":
            return node
    return None


def image_linked_to_socket(socket):
    if not socket or not socket.is_linked:
        return None
    stack = [link.from_node for link in socket.links]
    seen = set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if node.bl_idname == "ShaderNodeTexImage" and image_is_loaded(node.image):
            return node.image
        for input_socket in node.inputs:
            for link in input_socket.links:
                stack.append(link.from_node)
    return None


def find_by_socket(material, socket_names):
    principled = find_principled(material)
    if not principled:
        return None
    for name in socket_names:
        socket = principled.inputs.get(name)
        image = image_linked_to_socket(socket)
        if image:
            return image
    return None


def find_by_keywords(material, keywords, reject=()):
    for _node, image, text in image_candidates(material):
        if any(word in text for word in reject):
            continue
        if any(word in text for word in keywords):
            return image
    return None


def find_map(material, map_type):
    if map_type == "base":
        return (
            find_by_socket(material, ("Base Color", "BaseColor"))
            or find_by_keywords(material, ("_bc", "_bcr", "basecolor", "base_color", "albedo", "diffuse", "color"), ("rough", "normal", "metal", "ao", "occlusion"))
        )
    if map_type == "roughness":
        return (
            find_by_socket(material, ("Roughness",))
            or find_by_keywords(material, ("roughness", "rough", "_rgh", "_bcr"))
        )
    if map_type == "normal":
        return (
            find_by_socket(material, ("Normal",))
            or find_by_keywords(material, ("normal", "_nmo", "_nrm", "_n."), ("rough", "metal"))
        )
    if map_type == "metalness":
        return (
            find_by_socket(material, ("Metallic", "Metalness"))
            or find_by_keywords(material, ("metallic", "metalness", "metal", "_m", "_nmo"))
        )
    if map_type == "ao":
        return find_by_keywords(material, ("ambientocclusion", "ambient_occlusion", "occlusion", "_ao", "_occ", "_nmo"))
    return None


def image_pixels(image):
    width, height = image.size
    pixels = list(image.pixels[:])
    return width, height, pixels


def sample_channel(image_data, x, y, channel, fallback):
    if not image_data:
        return fallback
    width, height, pixels, target_width, target_height = image_data
    sx = min(width - 1, int(x * width / target_width))
    sy = min(height - 1, int(y * height / target_height))
    idx = (sy * width + sx) * 4 + channel
    if idx < 0 or idx >= len(pixels):
        return fallback
    return pixels[idx]


def prepared_image(image, target_width, target_height):
    if not image:
        return None
    width, height, pixels = image_pixels(image)
    return width, height, pixels, target_width, target_height


def output_size(images, fallback_size):
    sizes = [tuple(image.size) for image in images if image]
    if not sizes:
        return fallback_size, fallback_size
    return max(sizes, key=lambda size: size[0] * size[1])


def save_packed_image(name, width, height, pixels, export_dir, file_format):
    os.makedirs(export_dir, exist_ok=True)
    image = bpy.data.images.new(name=name, width=width, height=height, alpha=True, float_buffer=False)
    image.pixels.foreach_set(pixels)
    extension = ".tif" if file_format == "TIFF" else ".png"
    path = os.path.join(export_dir, name + extension)
    image.filepath_raw = path
    image.file_format = file_format
    image.save()
    bpy.data.images.remove(image)
    return path


def pack_bcr(material, export_dir, file_format, fallback_size):
    base = find_map(material, "base")
    roughness = find_map(material, "roughness")
    width, height = output_size((base, roughness), fallback_size)
    base_data = prepared_image(base, width, height)
    rough_data = prepared_image(roughness, width, height)

    pixels = [0.0] * (width * height * 4)
    for y in range(height):
        for x in range(width):
            out = (y * width + x) * 4
            pixels[out + 0] = sample_channel(base_data, x, y, 0, 1.0)
            pixels[out + 1] = sample_channel(base_data, x, y, 1, 1.0)
            pixels[out + 2] = sample_channel(base_data, x, y, 2, 1.0)
            pixels[out + 3] = sample_channel(rough_data, x, y, 0, 0.5)
    return save_packed_image(clean_name(material.name) + "_BCR", width, height, pixels, export_dir, file_format)


def pack_nmo(material, export_dir, file_format, fallback_size, invert_green):
    normal = find_map(material, "normal")
    metalness = find_map(material, "metalness")
    ao = find_map(material, "ao")
    width, height = output_size((normal, metalness, ao), fallback_size)
    normal_data = prepared_image(normal, width, height)
    metal_data = prepared_image(metalness, width, height)
    ao_data = prepared_image(ao, width, height)

    pixels = [0.0] * (width * height * 4)
    for y in range(height):
        for x in range(width):
            out = (y * width + x) * 4
            green = sample_channel(normal_data, x, y, 1, 0.5)
            pixels[out + 0] = sample_channel(normal_data, x, y, 0, 0.5)
            pixels[out + 1] = 1.0 - green if invert_green else green
            pixels[out + 2] = sample_channel(metal_data, x, y, 0, 0.0)
            pixels[out + 3] = sample_channel(ao_data, x, y, 0, 1.0)
    return save_packed_image(clean_name(material.name) + "_NMO", width, height, pixels, export_dir, file_format)


class ENFUSION_TEXPACK_Properties(bpy.types.PropertyGroup):
    export_dir: bpy.props.StringProperty(
        name="Export Directory",
        subtype="DIR_PATH",
        default="//efc_export",
    )
    file_format: bpy.props.EnumProperty(
        name="Format",
        items=(("TIFF", "TIFF", "Preferred Enfusion source format"), ("PNG", "PNG", "Portable fallback format")),
        default="TIFF",
    )
    fallback_size: bpy.props.EnumProperty(
        name="Fallback Size",
        items=(("512", "512", ""), ("1024", "1024", ""), ("2048", "2048", ""), ("4096", "4096", "")),
        default="2048",
    )
    pack_bcr: bpy.props.BoolProperty(name="BCR", default=True)
    pack_nmo: bpy.props.BoolProperty(name="NMO", default=True)
    invert_normal_green: bpy.props.BoolProperty(
        name="DirectX Normal -Y",
        description="Invert normal green channel for Enfusion DirectX normal convention",
        default=True,
    )


class ENFUSION_OT_pack_textures(bpy.types.Operator):
    bl_idname = "enfusion.pack_bcr_nmo_textures"
    bl_label = "Pack Selected Materials"
    bl_description = "Pack selected mesh materials to Enfusion _BCR and _NMO textures"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        props = context.scene.enfusion_texture_packer
        export_dir = bpy.path.abspath(props.export_dir)
        fallback_size = int(props.fallback_size)
        materials = material_slots_from_selection(context)
        if not materials:
            self.report({"ERROR"}, "Selected meshes have no materials")
            return {"CANCELLED"}

        written = []
        for material in materials:
            if props.pack_bcr:
                written.append(pack_bcr(material, export_dir, props.file_format, fallback_size))
            if props.pack_nmo:
                written.append(pack_nmo(material, export_dir, props.file_format, fallback_size, props.invert_normal_green))

        self.report({"INFO"}, f"Wrote {len(written)} Enfusion texture(s) to {export_dir}")
        for path in written:
            print("ENFUSION_TEXTURE_PACKED", path)
        return {"FINISHED"}


class ENFUSION_PT_texture_packer(bpy.types.Panel):
    bl_label = "Texture Packer"
    bl_idname = "ENFUSION_PT_texture_packer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Enfusion"

    def draw(self, context):
        props = context.scene.enfusion_texture_packer
        layout = self.layout
        layout.prop(props, "export_dir")
        row = layout.row(align=True)
        row.prop(props, "pack_bcr", toggle=True)
        row.prop(props, "pack_nmo", toggle=True)
        layout.prop(props, "file_format")
        layout.prop(props, "fallback_size")
        layout.prop(props, "invert_normal_green")
        layout.operator(ENFUSION_OT_pack_textures.bl_idname)


classes = (
    ENFUSION_TEXPACK_Properties,
    ENFUSION_OT_pack_textures,
    ENFUSION_PT_texture_packer,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.enfusion_texture_packer = bpy.props.PointerProperty(type=ENFUSION_TEXPACK_Properties)


def unregister():
    del bpy.types.Scene.enfusion_texture_packer
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
