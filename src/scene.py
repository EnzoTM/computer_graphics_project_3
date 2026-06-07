"""Montagem da cena e ordem de renderização — Projeto 3: Iluminação Phong.

Mantém toda a geometria e lógica do P2, acrescido de:
  * Dois programas Phong: phong_ext (exterior, 1 luz) e phong_int (interior, 2 luzes).
  * LightState: toggles e intensidades controláveis pelo teclado.
  * Objetos separados em ext_objects / int_objects.
  * Medusa (jelly_fish) como fonte de luz exterior, movível pelas setas.
  * Lampada industrial no teto da cabine como luz interior principal.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_DEPTH_TEST,
    GL_ELEMENT_ARRAY_BUFFER,
    GL_FALSE,
    GL_FLOAT,
    GL_LEQUAL,
    GL_LESS,
    GL_STATIC_DRAW,
    GL_TEXTURE0,
    GL_TEXTURE_2D,
    GL_TRIANGLES,
    GL_UNSIGNED_INT,
    glActiveTexture,
    glBindBuffer,
    glBindTexture,
    glBindVertexArray,
    glBufferData,
    glDepthFunc,
    glDrawElements,
    glEnable,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenVertexArrays,
    glVertexAttribPointer,
)

import utils
from model import Model, SubMesh, ctypes_offset, draw_model
from shader import Program
from texture import load_texture_2d


# --------------------------------------------------------------------------- #
#  Primitivas geométricas geradas em runtime                                   #
# --------------------------------------------------------------------------- #


def _make_textured_model(
    vertex_data: list[float],
    indices: list[int],
    diffuse_path: str,
    wrap_repeat: bool = True,
    name: str = "primitive",
) -> Model:
    """Constrói um Model com uma única submalha.

    Formato de vertex_data: 8 floats por vértice [x, y, z, u, v, nx, ny, nz].
    """
    vao = int(glGenVertexArrays(1))
    vbo = int(glGenBuffers(1))
    ebo = int(glGenBuffers(1))
    glBindVertexArray(vao)

    vbo_data = np.asarray(vertex_data, dtype=np.float32)
    ebo_data = np.asarray(indices, dtype=np.uint32)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, vbo_data.nbytes, vbo_data, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, ebo_data.nbytes, ebo_data, GL_STATIC_DRAW)

    stride = 8 * 4  # x, y, z, u, v, nx, ny, nz
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
    glEnableVertexAttribArray(1)
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes_offset(3 * 4))
    glEnableVertexAttribArray(2)
    glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, ctypes_offset(5 * 4))
    glBindVertexArray(0)

    tex = load_texture_2d(diffuse_path, wrap_repeat=wrap_repeat)
    sub = SubMesh(diffuse_tex=tex, index_offset=0, index_count=len(indices), material_name=name)
    return Model(vao=vao, submeshes=[sub], name=name)


def make_floor(size: float, tex_path: str, tile: float, y: float = 0.0) -> Model:
    h = size / 2.0
    verts = [
        -h, y, -h,  0.0,  0.0,   0.0, 1.0, 0.0,
         h, y, -h,  tile, 0.0,   0.0, 1.0, 0.0,
         h, y,  h,  tile, tile,  0.0, 1.0, 0.0,
        -h, y,  h,  0.0,  tile,  0.0, 1.0, 0.0,
    ]
    inds = [0, 1, 2, 0, 2, 3]
    return _make_textured_model(verts, inds, tex_path, name="floor")


def make_hull_following_floor(
    obj_path: str,
    sub_scale: float,
    sub_translation_y: float,
    target_y_world: float,
    margin: float,
    tex_path: str,
    tile_density_x: float = 0.5,
    tile_density_z: float = 0.5,
    z_band: float = 0.18,
    name: str = "hull_floor",
) -> Model:
    target_y_local = (target_y_world - sub_translation_y) / sub_scale

    bins: dict[int, float] = {}
    with open(obj_path) as fin:
        for ln in fin:
            if not ln.startswith("v "):
                continue
            _, sx, sy, sz = ln.split()[:4]
            x_local = float(sx)
            y_local = float(sy)
            z_local = float(sz)
            if abs(y_local - target_y_local) > 0.15:
                continue
            z_world = z_local * sub_scale
            x_world = abs(x_local * sub_scale)
            zi = round(z_world)
            if x_world > bins.get(zi, 0.0):
                bins[zi] = x_world

    if not bins:
        raise RuntimeError(
            f"make_hull_following_floor: no hull vertices found near "
            f"Y_local={target_y_local:.2f} (Y_world={target_y_world})"
        )

    min_half_width = 1.5
    samples: list[tuple[float, float]] = []
    for zi in sorted(bins):
        hw = bins[zi] - margin
        if hw < min_half_width:
            continue
        samples.append((float(zi), hw))

    if len(samples) < 2:
        raise RuntimeError("make_hull_following_floor: too few usable Z slices")

    z_first = samples[0][0]
    z_last = samples[-1][0]
    total_len_z = z_last - z_first
    print(
        f"[scene] hull-following floor: {len(samples)} slices, "
        f"Z∈[{z_first:.0f},{z_last:.0f}] ({total_len_z:.0f}m), "
        f"max half-width={max(hw for _, hw in samples):.2f}m"
    )

    verts: list[float] = []
    for z, hw in samples:
        v_v = (z - z_first) * tile_density_z
        u_l = 0.0
        u_r = (2.0 * hw) * tile_density_x
        # Borda esquerda, normal +Y
        verts.extend([-hw, 0.0, z, u_l, v_v, 0.0, 1.0, 0.0])
        # Borda direita, normal +Y
        verts.extend([+hw, 0.0, z, u_r, v_v, 0.0, 1.0, 0.0])

    inds: list[int] = []
    for i in range(len(samples) - 1):
        a = 2 * i
        b = 2 * i + 1
        c = 2 * (i + 1)
        d = 2 * (i + 1) + 1
        inds.extend([a, b, d, a, d, c])

    return _make_textured_model(verts, inds, tex_path, name=name)


def make_sky_sphere(radius: float = 250.0, segments: int = 48, rings: int = 24) -> tuple[int, int]:
    """Esfera para o skydome — NÃO alterada: apenas posição (sem normal/UV)."""
    verts: list[float] = []
    inds: list[int] = []
    for r in range(rings + 1):
        phi = math.pi * r / rings
        for s in range(segments + 1):
            theta = 2.0 * math.pi * s / segments
            x = math.sin(phi) * math.cos(theta) * radius
            y = math.cos(phi) * radius
            z = math.sin(phi) * math.sin(theta) * radius
            verts.extend([x, y, z])
    for r in range(rings):
        for s in range(segments):
            i0 = r * (segments + 1) + s
            i1 = i0 + 1
            i2 = i0 + (segments + 1)
            i3 = i2 + 1
            inds.extend([i0, i2, i1, i1, i2, i3])

    vao = int(glGenVertexArrays(1))
    vbo = int(glGenBuffers(1))
    ebo = int(glGenBuffers(1))
    glBindVertexArray(vao)
    vbo_data = np.asarray(verts, dtype=np.float32)
    ebo_data = np.asarray(inds, dtype=np.uint32)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, vbo_data.nbytes, vbo_data, GL_STATIC_DRAW)
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, ebo_data.nbytes, ebo_data, GL_STATIC_DRAW)

    stride = 3 * 4
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, None)
    glBindVertexArray(0)
    return vao, len(inds)


# --------------------------------------------------------------------------- #
#  Descrição da cena                                                          #
# --------------------------------------------------------------------------- #


@dataclass
class Object3D:
    model: Model
    translation: tuple[float, float, float]
    rotation_y: float = 0.0
    scale_xyz: tuple[float, float, float] = (1.0, 1.0, 1.0)
    extra_rotation: callable | None = None
    extra_translation: callable | None = None
    uv_tile: float = 1.0
    ka:        float = 0.2
    kd:        float = 0.7
    ks:        float = 0.3
    shininess: float = 32.0

    def model_matrix(self) -> np.ndarray:
        m = utils.translate(*self.translation)
        if self.extra_translation is not None:
            m = m @ self.extra_translation()
        m = m @ utils.rotate_y(self.rotation_y)
        if self.extra_rotation is not None:
            m = m @ self.extra_rotation()
        m = m @ utils.scale(*self.scale_xyz)
        return m


@dataclass
class LightState:
    # Luz direcional da água — simula luz solar filtrada pela superfície.
    # Direção aponta DE BAIXO PARA CIMA (para a fonte), com leve inclinação.
    water_on:    bool  = True
    water_dir:   tuple = (0.15, 1.0, 0.05)   # normalizado no shader
    water_color: tuple = (0.25, 0.70, 0.90)  # azul-esverdeado subaquático

    # Luz exterior: medusa (posição dinâmica, atualizada com movimento)
    jelly_on:    bool  = True
    jelly_color: tuple = (0.1, 0.9, 0.7)

    # Luz interior 1: lampada — posicionada na base da luminária (world y≈8.33)
    lamp_on:    bool  = True
    lamp_pos:   tuple = (0.0, 8.0, 1.0)
    lamp_color: tuple = (1.0, 0.95, 0.8)

    # Luz interior 2: monitor da estação de trabalho — world z≈19.5
    monitor_on:    bool  = True
    monitor_pos:   tuple = (0.0, 4.20, 19.50)
    monitor_color: tuple = (0.2, 0.5, 1.0)

    # Globais ajustáveis por teclado
    ambient:       float = 0.45
    diffuse_mult:  float = 1.0
    specular_mult: float = 1.0


class Scene:
    def __init__(self) -> None:
        self.phong_ext = Program.from_files(
            utils.asset("shaders", "phong_ext.vert"),
            utils.asset("shaders", "phong_ext.frag"),
            label="phong_ext",
        )
        self.phong_int = Program.from_files(
            utils.asset("shaders", "phong_int.vert"),
            utils.asset("shaders", "phong_int.frag"),
            label="phong_int",
        )
        self.sky_program = Program.from_files(
            utils.asset("shaders", "skydome.vert"),
            utils.asset("shaders", "skydome.frag"),
            label="skydome",
        )

        self.sky_vao, self.sky_indices = make_sky_sphere(radius=250.0)
        self.sky_tex = load_texture_2d(
            utils.asset("assets", "texturas", "skybox", "skyrender.png"),
            wrap_repeat=False,
            flip_y=True,
        )

        sand_path = utils.asset("assets", "texturas", "chao_externo", "coast_sand_05_diff_4k.jpg")
        metal_path = utils.asset("assets", "texturas", "interior", "metal_brushed.jpg")

        self.outdoor_floor = make_floor(size=400.0, tex_path=sand_path, tile=40.0, y=0.0)

        self.indoor_floor = make_hull_following_floor(
            obj_path=utils.asset("assets", "modelos", "submarino", "submarino.obj"),
            sub_scale=2.5,
            sub_translation_y=5.55,
            target_y_world=3.5,
            margin=0.50,
            tex_path=metal_path,
            tile_density_x=0.5,
            tile_density_z=0.5,
            name="indoor_floor",
        )
        self.indoor_floor_offset = (0.0, 3.5, 0.0)

        def load(name: str, fallback: str | None = None) -> Model:
            path = utils.asset("assets", "modelos", name, f"{name}.obj")
            return Model.load_obj(path, fallback_texture=fallback)

        # A lampada tem 4 materiais, mas só "Metal" possui map_Kd; usamos o albedo
        # de aço escovado como fallback para que Glass/Light/Cable não fiquem magenta.
        lamp_fallback = utils.asset(
            "assets", "modelos", "lamp", "TexturesCom_Metal_SteelBrushed_1K_albedo.tif"
        )

        models = {
            "submarino": load("submarino"),
            "coral": load("coral"),
            "pedra": load("pedra"),
            "alga": load("alga"),
            "cadeira": load("cadeira"),
            "estacao": load("estacao"),
            "mesa": load("mesa"),
            "joystick": load("joystick_2"),
            "peixe_palhaco": load("peixe_palhaco"),
            "orca": load("orca"),
            "beluga": load("beluga"),
            "lamp": load("lamp", lamp_fallback),
            "jelly_fish": load("jelly_fish"),
        }

        # Objetos exteriores e interiores separados
        self.ext_objects: list[Object3D] = []
        self.int_objects: list[Object3D] = []

        # Submarino
        SUB_SCALE = 2.5
        self.submarine_scale = SUB_SCALE
        sub_length = (8.66 + 10.07) * SUB_SCALE
        sub_width = (1.82 * 2) * SUB_SCALE
        sub_height = (4.86 + 1.82) * SUB_SCALE
        sub_y = 1.82 * SUB_SCALE + 1.0
        print(
            f"[scene] submarine scale={SUB_SCALE} -> length≈{sub_length:.1f}m "
            f"width≈{sub_width:.1f}m height≈{sub_height:.1f}m"
        )
        # O submarino é o limite entre interior e exterior: é desenhado no passe
        # interior (paredes internas reagem à lampada/monitor via iluminação de
        # dois lados) e recebe adicionalmente a luz da medusa (uLight3) para que
        # o casco externo continue reagindo à fonte exterior.
        self.submarine_obj = Object3D(
            model=models["submarino"],
            translation=(0.0, sub_y, 0.0),
            rotation_y=0.0,
            scale_xyz=(SUB_SCALE, SUB_SCALE, SUB_SCALE),
            ka=0.2, kd=0.7, ks=0.5, shininess=64.0,
        )
        self.int_objects.append(self.submarine_obj)

        # Decoração procedural do leito marinho
        self._populate_decor_grid(
            models=models,
            cell_size=10.0,
            x_range=(-200.0, 200.0),
            z_range=(-200.0, 200.0),
            cell_step=3,
            sub_exclusion_half=(6.0, 25.0),
            reserved_cells=(),
            coral_scale_range=(0.045, 0.110),
            pedra_scale_range=(0.10, 0.32),
            alga_scale_range=(0.5, 1.4),
            coral_count_range=(0, 1),
            pedra_count_range=(0, 1),
            alga_count_range=(0, 1),
            min_pair_distance=2.5,
            seed=42,
        )

        # Cardume de peixes-palhaço
        self._populate_fish_grid(
            models=models,
            model_key="peixe_palhaco",
            cell_size=10.0,
            x_range=(-200.0, 200.0),
            z_range=(-200.0, 200.0),
            cell_step=6,
            count_range=(1, 3),
            sub_exclusion_half=(6.0, 25.0),
            y_range=(1.5, 9.0),
            scale_range=(0.35, 0.60),
            seed=137,
        )

        # Orca
        self.orca_base_scale = 1.7
        self.orca_obj = Object3D(
            model=models["orca"],
            translation=(45.0, 14.0, 25.0),
            rotation_y=math.radians(180.0 + 30.0),
            scale_xyz=(self.orca_base_scale,) * 3,
            ka=0.3, kd=0.8, ks=0.2, shininess=16.0,
        )
        self.ext_objects.append(self.orca_obj)

        # Beluga
        beluga_scale = 0.16
        beluga_y_offset = -10.0 * beluga_scale
        self.beluga_obj = Object3D(
            model=models["beluga"],
            translation=(-35.0, 12.0 + beluga_y_offset, -15.0),
            rotation_y=math.radians(-45.0),
            scale_xyz=(beluga_scale, beluga_scale, beluga_scale),
            ka=0.3, kd=0.8, ks=0.2, shininess=16.0,
        )
        self.beluga_base_rotation_y = self.beluga_obj.rotation_y
        self.ext_objects.append(self.beluga_obj)

        # Medusa (fonte de luz exterior)
        self.jelly_pos = [20.0, 6.0, 35.0]
        self.jelly_obj = Object3D(
            model=models["jelly_fish"],
            translation=tuple(self.jelly_pos),
            rotation_y=0.0,
            scale_xyz=(2.0, 2.0, 2.0),
            ka=0.4, kd=0.6, ks=0.5, shininess=32.0,
        )
        self.ext_objects.append(self.jelly_obj)

        # ============================================================
        #  Cabine de comando (interior)
        # ============================================================
        cockpit_chair_z = 16.0
        chair_scale = 0.25
        chair_floor_y = 3.5
        chair_local_base_y = -0.14
        chair_local_center_z = (-5.19 + -1.65) / 2.0
        chair_y = chair_floor_y - chair_local_base_y * chair_scale
        chair_z = cockpit_chair_z - chair_local_center_z * chair_scale
        self.chair_base_translation = (0.0, chair_y, chair_z + 2.0)
        self.chair_obj = Object3D(
            model=models["cadeira"],
            translation=self.chair_base_translation,
            rotation_y=math.radians(0.0),
            scale_xyz=(chair_scale, chair_scale, chair_scale),
            ka=0.2, kd=0.6, ks=0.5, shininess=32.0,
        )
        self.int_objects.append(self.chair_obj)

        self.int_objects.append(Object3D(
            model=models["estacao"],
            translation=(0.0, 3.5, chair_z + 2.6),
            rotation_y=math.radians(90.0),
            scale_xyz=(1.0, 1.0, 1.0),
            ka=0.2, kd=0.6, ks=0.6, shininess=48.0,
        ))

        mesa_scale = 0.002
        mesa_floor_y = 3.5
        mesa_local_base_y = -6.201
        mesa_local_center_z = 0.0
        mesa_world_z = -10.0
        mesa_y = mesa_floor_y - mesa_local_base_y * mesa_scale
        mesa_z = mesa_world_z - mesa_local_center_z * mesa_scale
        self.int_objects.append(Object3D(
            model=models["mesa"],
            translation=(0.0, mesa_y, mesa_z),
            rotation_y=math.radians(180.0),
            scale_xyz=(mesa_scale, mesa_scale, mesa_scale),
            ka=0.2, kd=0.5, ks=0.7, shininess=64.0,
        ))

        joystick_scale = 0.04
        joystick_target_base_y = 4.10
        joystick_target_z = chair_z + 2.10
        self.int_objects.append(Object3D(
            model=models["joystick"],
            translation=(0.0, joystick_target_base_y, joystick_target_z),
            rotation_y=0.0,
            scale_xyz=(joystick_scale, joystick_scale, joystick_scale),
            ka=0.2, kd=0.6, ks=0.8, shininess=128.0,
        ))

        # Lampada no teto
        lamp_scale = 1.0
        self.lamp_obj = Object3D(
            model=models["lamp"],
            translation=(0.0, 8.0, 1.0),
            rotation_y=0.0,
            scale_xyz=(lamp_scale, lamp_scale, lamp_scale),
            ka=0.3, kd=0.5, ks=0.9, shininess=128.0,
        )
        self.int_objects.append(self.lamp_obj)

        # Estado de iluminação
        self.lights = LightState()

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)

    # ============================================================
    #  Decoração procedural
    # ============================================================

    def _populate_decor_grid(
        self,
        models: dict,
        cell_size: float,
        x_range: tuple,
        z_range: tuple,
        sub_exclusion_half: tuple,
        reserved_cells: tuple,
        coral_scale_range: tuple,
        pedra_scale_range: tuple,
        min_pair_distance: float,
        seed: int,
        cell_step: int = 1,
        coral_count_range: tuple = (1, 1),
        pedra_count_range: tuple = (1, 1),
        alga_scale_range: tuple = (0.4, 1.2),
        alga_count_range: tuple = (0, 0),
    ) -> None:
        rng = random.Random(seed)

        x0, x1 = x_range
        z0, z1 = z_range
        nx = max(1, int(round((x1 - x0) / cell_size)))
        nz = max(1, int(round((z1 - z0) / cell_size)))
        cell_step = max(1, int(cell_step))

        ix_offset = (nx // 2) % cell_step
        iz_offset = (nz // 2) % cell_step

        sx_half, sz_half = sub_exclusion_half
        reserved_centers = []
        for rx, rz in reserved_cells:
            ix = int((rx - x0) // cell_size)
            iz = int((rz - z0) // cell_size)
            cx = x0 + (ix + 0.5) * cell_size
            cz = z0 + (iz + 0.5) * cell_size
            reserved_centers.append((cx, cz))

        jitter = cell_size * 0.35
        coral_min, coral_max = coral_count_range
        pedra_min, pedra_max = pedra_count_range
        alga_min, alga_max = alga_count_range
        placed_coral = placed_pedra = placed_alga = 0
        empty_cells = skipped_sub = skipped_reserved = skipped_step = 0

        for ix in range(nx):
            for iz in range(nz):
                if (ix - ix_offset) % cell_step != 0 \
                        or (iz - iz_offset) % cell_step != 0:
                    skipped_step += 1
                    continue

                cx = x0 + (ix + 0.5) * cell_size
                cz = z0 + (iz + 0.5) * cell_size

                if abs(cx) < sx_half and abs(cz) < sz_half:
                    skipped_sub += 1
                    continue
                if any(abs(cx - rcx) < 1e-3 and abs(cz - rcz) < 1e-3
                       for rcx, rcz in reserved_centers):
                    skipped_reserved += 1
                    continue

                n_coral = rng.randint(coral_min, coral_max)
                n_pedra = rng.randint(pedra_min, pedra_max)
                n_alga = rng.randint(alga_min, alga_max)

                first_coral_xz: tuple[float, float] | None = None
                for _ in range(n_coral):
                    coral_x = cx + rng.uniform(-jitter, jitter)
                    coral_z = cz + rng.uniform(-jitter, jitter)
                    coral_s = rng.uniform(*coral_scale_range)
                    coral_rot = rng.uniform(0.0, 360.0)
                    self.ext_objects.append(Object3D(
                        model=models["coral"],
                        translation=(coral_x, 0.0, coral_z),
                        rotation_y=math.radians(coral_rot),
                        scale_xyz=(coral_s, coral_s, coral_s),
                        ka=0.3, kd=0.7, ks=0.1, shininess=8.0,
                    ))
                    if first_coral_xz is None:
                        first_coral_xz = (coral_x, coral_z)
                    placed_coral += 1

                for k in range(n_pedra):
                    pedra_x = cx + rng.uniform(-jitter, jitter)
                    pedra_z = cz + rng.uniform(-jitter, jitter)
                    if k == 0 and first_coral_xz is not None:
                        for _ in range(6):
                            if (pedra_x - first_coral_xz[0]) ** 2 \
                                    + (pedra_z - first_coral_xz[1]) ** 2 \
                                    >= min_pair_distance ** 2:
                                break
                            pedra_x = cx + rng.uniform(-jitter, jitter)
                            pedra_z = cz + rng.uniform(-jitter, jitter)
                    pedra_s = rng.uniform(*pedra_scale_range)
                    pedra_rot = rng.uniform(0.0, 360.0)
                    self.ext_objects.append(Object3D(
                        model=models["pedra"],
                        translation=(pedra_x, 0.0, pedra_z),
                        rotation_y=math.radians(pedra_rot),
                        scale_xyz=(pedra_s, pedra_s, pedra_s),
                        ka=0.2, kd=0.6, ks=0.1, shininess=8.0,
                    ))
                    placed_pedra += 1

                for _ in range(n_alga):
                    alga_x = cx + rng.uniform(-jitter, jitter)
                    alga_z = cz + rng.uniform(-jitter, jitter)
                    alga_s = rng.uniform(*alga_scale_range)
                    alga_rot = rng.uniform(0.0, 360.0)
                    self.ext_objects.append(Object3D(
                        model=models["alga"],
                        translation=(alga_x, 0.0, alga_z),
                        rotation_y=math.radians(alga_rot),
                        scale_xyz=(alga_s, alga_s, alga_s),
                        ka=0.3, kd=0.7, ks=0.05, shininess=4.0,
                    ))
                    placed_alga += 1

                if n_coral == 0 and n_pedra == 0 and n_alga == 0:
                    empty_cells += 1

        print(
            f"[scene] decor grid: {nx}x{nz} cells (step={cell_step}), "
            f"placed {placed_coral} corais + {placed_pedra} pedras "
            f"+ {placed_alga} algas "
            f"(skipped {skipped_sub} sub, {skipped_reserved} reserved, "
            f"{skipped_step} by step, {empty_cells} empty)"
        )

    def _populate_fish_grid(
        self,
        models: dict,
        model_key: str,
        cell_size: float,
        x_range: tuple,
        z_range: tuple,
        cell_step: int,
        count_range: tuple,
        sub_exclusion_half: tuple,
        y_range: tuple,
        scale_range: tuple,
        seed: int,
    ) -> None:
        rng = random.Random(seed)

        x0, x1 = x_range
        z0, z1 = z_range
        nx = max(1, int(round((x1 - x0) / cell_size)))
        nz = max(1, int(round((z1 - z0) / cell_size)))
        cell_step = max(1, int(cell_step))

        ix_offset = (nx // 2) % cell_step
        iz_offset = (nz // 2) % cell_step

        sx_half, sz_half = sub_exclusion_half
        n_min, n_max = count_range
        y_min, y_max = y_range
        s_min, s_max = scale_range
        jitter = cell_size * 0.40
        placed = 0
        skipped_sub = 0

        for ix in range(nx):
            for iz in range(nz):
                if (ix - ix_offset) % cell_step != 0 \
                        or (iz - iz_offset) % cell_step != 0:
                    continue

                cx = x0 + (ix + 0.5) * cell_size
                cz = z0 + (iz + 0.5) * cell_size

                if abs(cx) < sx_half and abs(cz) < sz_half:
                    skipped_sub += 1
                    continue

                count = rng.randint(n_min, n_max)
                for _ in range(count):
                    fx = cx + rng.uniform(-jitter, jitter)
                    fz = cz + rng.uniform(-jitter, jitter)
                    fy = rng.uniform(y_min, y_max)
                    fs = rng.uniform(s_min, s_max)
                    frot = rng.uniform(0.0, 360.0)
                    self.ext_objects.append(Object3D(
                        model=models[model_key],
                        translation=(fx, fy, fz),
                        rotation_y=math.radians(frot),
                        scale_xyz=(fs, fs, fs),
                        ka=0.3, kd=0.8, ks=0.1, shininess=8.0,
                    ))
                    placed += 1

        print(
            f"[scene] fish grid ({model_key}): {nx}x{nz} cells "
            f"(step={cell_step}), placed {placed} fish "
            f"(skipped {skipped_sub} sub)"
        )

    JELLY_STEP = 0.5

    def translate_jelly_step(self, dx: float = 0.0, dz: float = 0.0) -> None:
        self.jelly_pos[0] += dx
        self.jelly_pos[2] += dz
        self.jelly_obj.translation = tuple(self.jelly_pos)

    def update(self, dt: float) -> None:
        return

    # ============================================================
    #  Renderização
    # ============================================================

    def draw(self, view: np.ndarray, proj: np.ndarray, cam_pos: np.ndarray) -> None:
        # ---- 1) Skydome — INALTERADO ----
        glDepthFunc(GL_LEQUAL)
        self.sky_program.use()
        self.sky_program.set_mat4("uView", view)
        self.sky_program.set_mat4("uProj", proj)
        self.sky_program.set_int("uPanorama", 0)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.sky_tex)
        glBindVertexArray(self.sky_vao)
        glDrawElements(GL_TRIANGLES, self.sky_indices, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        glDepthFunc(GL_LESS)

        cx, cy, cz = float(cam_pos[0]), float(cam_pos[1]), float(cam_pos[2])

        def setup_phong_common(prog: Program) -> None:
            prog.use()
            prog.set_mat4("uView", view)
            prog.set_mat4("uProj", proj)
            prog.set_int("uDiffuse", 0)
            prog.set_float("uUVTile", 1.0)
            prog.set_vec3("uCamPos", cx, cy, cz)
            prog.set_float("uAmbientIntensity", self.lights.ambient)
            prog.set_float("uDiffuseMult",      self.lights.diffuse_mult)
            prog.set_float("uSpecularMult",     self.lights.specular_mult)

        def set_material(prog: Program, obj: Object3D) -> None:
            prog.set_float("uKa",        obj.ka)
            prog.set_float("uKd",        obj.kd)
            prog.set_float("uKs",        obj.ks)
            prog.set_float("uShininess", obj.shininess)
            prog.set_float("uUVTile",    obj.uv_tile)

        # ================================================================
        # 2) CENA EXTERIOR — phong_ext
        # ================================================================
        setup_phong_common(self.phong_ext)

        # Luz direcional da água (vem de cima, simula luz solar subaquática)
        wx, wy, wz = self.lights.water_dir
        self.phong_ext.set_vec3("uWaterDir",   wx, wy, wz)
        self.phong_ext.set_vec3("uWaterColor", *self.lights.water_color)
        self.phong_ext.set_int ("uWaterOn",    int(self.lights.water_on))

        # Luz pontual da medusa
        jx, jy, jz = self.jelly_obj.translation
        self.phong_ext.set_vec3("uLightPos",   jx, jy, jz)
        self.phong_ext.set_vec3("uLightColor", *self.lights.jelly_color)
        self.phong_ext.set_int ("uLightOn",    int(self.lights.jelly_on))

        # Chão externo
        self.phong_ext.set_float("uKa", 0.3)
        self.phong_ext.set_float("uKd", 0.7)
        self.phong_ext.set_float("uKs", 0.1)
        self.phong_ext.set_float("uShininess", 16.0)
        self.phong_ext.set_float("uUVTile", 1.0)
        self.phong_ext.set_mat4("uModel", utils.identity())
        draw_model(self.outdoor_floor)

        for obj in self.ext_objects:
            set_material(self.phong_ext, obj)
            self.phong_ext.set_mat4("uModel", obj.model_matrix())
            draw_model(obj.model)

        # ================================================================
        # 3) CENA INTERIOR — phong_int
        # ================================================================
        setup_phong_common(self.phong_int)

        lx, ly, lz = self.lights.lamp_pos
        self.phong_int.set_vec3("uLight1Pos",   lx, ly, lz)
        self.phong_int.set_vec3("uLight1Color", *self.lights.lamp_color)
        self.phong_int.set_int ("uLight1On",    int(self.lights.lamp_on))

        mx, my, mz = self.lights.monitor_pos
        self.phong_int.set_vec3("uLight2Pos",   mx, my, mz)
        self.phong_int.set_vec3("uLight2Color", *self.lights.monitor_color)
        self.phong_int.set_int ("uLight2On",    int(self.lights.monitor_on))

        # Luz 3 = medusa: posição/cor sempre definidas. Só o casco do submarino
        # (uHullMode=1) a utiliza, e apenas na sua face externa.
        self.phong_int.set_vec3("uLight3Pos",   jx, jy, jz)
        self.phong_int.set_vec3("uLight3Color", *self.lights.jelly_color)
        self.phong_int.set_int ("uLight3On",    int(self.lights.jelly_on))

        if self.indoor_floor is not None:
            self.phong_int.set_int  ("uHullMode", 0)
            self.phong_int.set_float("uKa", 0.2)
            self.phong_int.set_float("uKd", 0.6)
            self.phong_int.set_float("uKs", 0.4)
            self.phong_int.set_float("uShininess", 64.0)
            self.phong_int.set_float("uUVTile", 1.0)
            self.phong_int.set_mat4("uModel", utils.translate(*self.indoor_floor_offset))
            draw_model(self.indoor_floor)

        for obj in self.int_objects:
            set_material(self.phong_int, obj)
            # Casco do submarino: modo de gating por face (exterior=medusa,
            # interior=luzes internas). Demais objetos: iluminação interior comum.
            self.phong_int.set_int("uHullMode", 1 if obj is self.submarine_obj else 0)
            self.phong_int.set_mat4("uModel", obj.model_matrix())
            draw_model(obj.model)
