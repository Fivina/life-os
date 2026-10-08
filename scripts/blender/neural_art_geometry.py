"""Curved volumetric neural tree, with branches rooted in their parent geometry."""
import random
from mathutils import Vector
from art_primitives import art_material, art_path, art_sphere


def build_neural_branches(root):
    rng = random.Random(572)
    near = art_material("V12_Neural_Primary", (0.32, 0.07, 0.6), 5.5, metallic=0)
    far = art_material("V12_Neural_Distant", (0.10, 0.017, 0.22), 2.0, metallic=0)
    tips = art_material("V12_Neural_Tips", (0.5, 0.17, 0.74), 5.0, metallic=0)
    seed = art_material("V19_Neural_Heart", (0.62, 0.26, 0.86), 6, metallic=0)
    front = Vector((0.1, -24.2, 11.5)).normalized()
    right = Vector((1, 0, 0))
    up = front.cross(right).normalized()

    def bezier(controls, t):
        a, b, c, d = controls
        return a * (1 - t) ** 3 + b * 3 * t * (1 - t) ** 2 + c * 3 * t * t * (1 - t) + d * t ** 3

    def world(v):
        return tuple(right * v.x + up * v.y + front * v.z)

    def bounded(v):
        return v.normalized() * 0.81 if v.length > 0.81 else v

    def curve(name, controls, width, material, samples=40):
        points = [world(bezier(controls, i / (samples - 1))) for i in range(samples)]
        obj = art_path(name, points, width, material, root)
        for i, point in enumerate(obj.data.splines[0].points):
            point.radius = 1 - 0.87 * i / (samples - 1)

    trunk = [Vector(v) for v in [(-0.035, -0.65, 0.38), (-0.16, -0.3, 0.55),
                                (0.07, 0.18, 0.25), (0.0, 0.69, 0.35)]]
    curve("Neural_Volumetric_Trunk", trunk, 0.031, near, 64)
    art_sphere("Neural_Growth_Heart", 0.026, seed, root, world(bezier(trunk, 0.19)), 16)
    for branch, (t0, x, y, depth) in enumerate([
        (0.18, -0.53, -0.11, -0.24), (0.26, 0.56, -0.05, 0.37),
        (0.38, -0.60, 0.2, 0.27), (0.47, 0.56, 0.31, -0.25),
        (0.56, -0.43, 0.49, -0.30), (0.64, 0.35, 0.59, 0.22),
        (0.74, -0.22, 0.67, -0.26), (0.82, 0.16, 0.72, 0.28),
    ]):
        start = bezier(trunk, t0)
        end = bounded(Vector((x, y, depth)))
        sign = 1 if x > 0 else -1
        controls = [start, bounded(start + Vector((sign * 0.22, 0.02, -0.15))),
                    bounded(end + Vector((-sign * 0.10, -0.24, 0.19))), end]
        material = far if depth < 0.2 else near
        curve("Neural_Depth_Branch_" + str(branch), controls, 0.018 - branch * 0.0008, material)
        for twig in range(7):
            attach = bezier(controls, 0.18 + twig * 0.115 + rng.uniform(-0.015, 0.015))
            wing = sign if twig % 3 else -sign
            target = bounded(attach + Vector((wing * rng.uniform(0.065, 0.18),
                                              rng.uniform(-0.035, 0.18), rng.uniform(-0.22, 0.20))))
            twig_controls = [attach, bounded(attach + Vector((wing * 0.06, 0.01, -0.055))),
                             bounded(target + Vector((-wing * 0.045, -0.045, 0.065))), target]
            curve("Neural_Depth_Twig_{}_{}".format(branch, twig), twig_controls, 0.004, material, 24)
            if twig % 2 == 0:
                art_sphere("Neural_Embedded_Node_{}_{}".format(branch, twig),
                           rng.uniform(0.01, 0.025), tips if target.z > 0.05 else far, root, world(target), 12)
            if twig >= 2:
                for leaf in range(2):
                    origin = bezier(twig_controls, 0.4 + leaf * 0.3)
                    destination = bounded(origin + Vector((-wing * rng.uniform(0.04, 0.10),
                                                           rng.uniform(0.035, 0.075), (leaf * 2 - 1) * 0.09)))
                    fine = [origin, bounded(origin + Vector((-wing * 0.035, 0.018, 0.02))),
                            bounded(destination + Vector((wing * 0.01, -0.02, 0))), destination]
                    curve("Neural_Fine_{}_{}_{}".format(branch, twig, leaf), fine, 0.002, material, 18)
    base = trunk[0]
    for index in range(5):
        sign = -1 if index % 2 else 1
        end = base + Vector((sign * (0.1 + index * 0.027), -0.03, -0.06 + index * 0.026))
        curve("Neural_Root_" + str(index), [base, base + Vector((sign * 0.03, -0.07, 0)),
                                           end + Vector((-sign * 0.025, -0.03, 0)), end], 0.008, near, 24)
