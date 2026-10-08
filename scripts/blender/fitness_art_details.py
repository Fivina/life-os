"""Machined plate-face details for the preserved Fitness pilot assembly."""
import math
from art_primitives import art_material, art_path, art_sphere


def finish_fitness_faces(root):
    satin = art_material("V4_Fitness_Satin_Faces", (0.12, 0.19, 0.24), 0, 0.36, 0.72)
    groove = art_material("V4_Fitness_Recessed_Grooves", (0.008, 0.018, 0.025), 0, 0.48, 0.6)
    hardware = art_material("V4_Fitness_Fasteners", (0.22, 0.29, 0.32), 0, 0.26, 0.85)
    for sign, side in [(-1, "Left"), (1, "Right")]:
        for index, radius in enumerate([0.78, 0.69, 0.58]):
            name = "Fitness_" + side + "Plate" + str(index)
            plate = next(obj for obj in root.children if obj.name == name)
            plate.data = plate.data.copy()
            plate.data.materials.clear()
            plate.data.materials.append(satin)
            x = sign * (1.83 + index * 0.17)
            for face in [-1, 1]:
                for channel, fraction in enumerate([0.51, 0.72]):
                    points = [(x + face * 0.072,
                               -1.16 + radius * fraction * math.cos(t),
                               0.61 + radius * fraction * math.sin(t))
                              for t in [i * math.tau / 128 for i in range(128)]]
                    art_path("Fitness_{}_{}_{}_Groove_{}".format(side, index, face, channel),
                             points, 0.006, groove, root, True)
                if index == 0:
                    for bolt in range(6):
                        t = bolt * math.tau / 6
                        art_sphere("Fitness_{}_{}_Fastener_{}".format(side, face, bolt),
                                   0.018, hardware, root,
                                   (x + face * 0.074, -1.16 + radius * 0.61 * math.cos(t),
                                    0.61 + radius * 0.61 * math.sin(t)), 12)
