#!/usr/bin/env python3.7
# coding: utf-8

# In[5]:


# Imports for the Maptek Python SDK and additional libraries.
import collections
import copy
import ctypes
import fractions
import functools
import math
import timeit
import time
import warnings
from fractions import Fraction
from collections import defaultdict
from itertools import compress, islice
from operator import itemgetter
import sys


import matplotlib as mpl
import matplotlib.colors as cc

# mpl.use('agg')
import matplotlib.pyplot as cm
import numpy as np
import pandas as pd

# import rtree
import seaborn as sns
from mapteksdk.data import (
    DenseBlockModel,
    GridSurface,
    NumericColourMap,
    PointSet,
    SubblockedBlockModel,
    Surface,
    Text3D,
)
from mapteksdk.project import Project
from matplotlib.ticker import PercentFormatter
from matplotlib.widgets import Button, CheckButtons, RadioButtons
from more_itertools import locate, seekable
from sklearn import metrics
from sklearn.metrics import confusion_matrix
from tqdm import tqdm_gui
from tqdm.auto import tqdm, trange
from trimesh import Trimesh
from trimesh.ray import ray_triangle
from trimesh.ray.ray_util import contains_points

warnings.filterwarnings("ignore", category=DeprecationWarning)

cm.rcParams["font.family"] = ["Source Han Sans TW", "monospace"]
cm.rcParams["font.size"] = 14

# Connect to the currently running Maptek Project.
project = Project()
# project.mcp_instance.mcp_dict['PRODUCT_LOCATION_INFO']  # Report out which application it connected to (Optional)


# In[6]:


# Initialisation
selected_model = None
selected_var = ""
colours = ""
real_colours = []
vis = ""
# ****************Bool swicthes for certain features*****************************************************************
vis_compiler = False
point_checker = True
# ********************************************************************************************************************
names = []
df = pd.DataFrame()
selection = project.get_selected()
last_opacity = 255


# Creating the array for storing data to be retrieved
global M
M = len(selection)
vis_collection = [0] * M
var_collection = [0] * M
index_map = [0] * M
number_of_parent_blocks = []
reverse_grid_index = []
block_model_names = []
totallength_y_dimension = []
totallength_x_dimension = []
totallength_z_dimension = []
x_res = []
y_res = []
z_res = []
x_count = []
y_count = []
z_count = []

extents = [[] for _ in range(M)]
# number_of_parent_blocks=[]
# i tells you the index of the block_model
i = 0
j = 0


# * This cod below collects some data(names of models) for immediate use and makes some
# * checks before program is started.
for name_iterator in selection:
    block_model_names.append(name_iterator.name)
    if (
        name_iterator.is_a(DenseBlockModel) == False
        and name_iterator.is_a(SubblockedBlockModel) == False
    ):
        print("Please select two Block Models to compare, Try Again.")
        time.sleep(3)
        sys.exit()


if len(selection) < 2:
    print("Please select two Block Models to compare, Try Again.")
    time.sleep(3)
    sys.exit()

print(
    "Enter X, Y and Z coordinates of the smallest subblock of "
    + str(block_model_names[0])
    + "(Format: X Y Z):"
)
smallest_sub_size_block1 = input()
smallest_sub_size_block1 = list(map(Fraction, smallest_sub_size_block1.split(" ")))
smallest_sub_size_block1 = list(map(float, smallest_sub_size_block1))

print(
    "Enter X, Y and Z coordinates of the smallest subblock of "
    + str(block_model_names[1])
    + " (Format: X Y Z):"
)
smallest_sub_size_block2 = input()
smallest_sub_size_block2 = list(map(Fraction, smallest_sub_size_block2.split(" ")))
smallest_sub_size_block2 = list(map(float, smallest_sub_size_block2))

solidfilter = "No"
solidfilter = input(
    "Do you want to restrict your search space inside a solid (Yes/No): "
)


if (solidfilter == "Yes") or (solidfilter == "Y") or (solidfilter == "y"):
    print(solidfilter)
    solidfilter = "Yes"
    solid_location = input("Put in the exact location of solid (ex:surfaces/Solid ) : ")
# DATA GETTER

for item in selection:
    print(item.name)
    # Setting outer array back to 0, for new block
    j = 0
    nn = 0

    selected_model = item
    # Checker for point stuff
    if point_checker:
        # Getting all block details
        with project.edit(selected_model) as bm:

            block_sizes = bm.block_sizes
            block_centroids = bm.block_centroids
            b = bm.block_resolution
            x_res.append(float(b[0]))
            y_res.append(float(b[1]))
            z_res.append(float(b[2]))

            x_count.append(bm.column_count)
            y_count.append(bm.row_count)
            z_count.append(bm.slice_count)

            totallength_x_dimension.append(x_res[0] * x_count[0])
            totallength_y_dimension.append(y_res[0] * y_count[0])
            totallength_z_dimension.append(z_res[0] * z_count[0])

            index_map[i] = bm.block_to_grid_index
            # index_map[i] = index_map[i].tolist()
            number_of_parent_blocks.append(len(np.unique(index_map[i], axis=0)))
            total_volume_of_block = (
                number_of_parent_blocks[i] * x_res[i] * y_res[i] * z_res[i]
            )

            # Creating a reverse grid index
            # *************************************************************************************************
            # ! This is the complex, slow method.
            # # Making keys for reverse_grid_index i.e all unique parent blocks
            # parent_block_indexes = np.unique(index_map[i], axis=0)

            # # Getting corresponding sub of those parent blocks
            # parent_block_sub_indexes = []
            # for parent_block_indexes_crawler in tqdm(
            #     parent_block_indexes,
            #     total=len(parent_block_indexes),
            #     desc="Progress",
            #     ncols=100,
            #     ascii=True,
            #     position=0,
            #     leave=True,

            # ):
            #     sub_bool_values = np.all(
            #         index_map[i] == (parent_block_indexes_crawler), axis=1
            #     )
            #     sub_indexes = np.where(sub_bool_values)[0]
            #     parent_block_sub_indexes.append(sub_indexes)

            # # Converting the keys to tuples and making the dict of reverse_grid_index
            # parent_block_indexes = [tuple(x) for x in parent_block_indexes]
            # reverse_grid_index.append(
            #     dict(zip(parent_block_indexes, parent_block_sub_indexes))
            # )
            # *****************************************************************
            # * This the better fast method.
            temp_dict_for_storing = {}
            for block, grid_index in tqdm(
                enumerate(index_map[i]),
                total=len(index_map[i]),
                desc="Progress",
                ncols=100,
                ascii=True,
                position=0,
                leave=True,
            ):
                # We want to use the grid_index as the dictionary key. It needs to
                # be converted to a tuple which can be hashed.
                # Also, the grid_index is returned from the SDK as a float array
                # which seems odd. So convert to an integer array as well.
                grid_index_tuple = tuple(grid_index.astype(int))
                if grid_index_tuple in temp_dict_for_storing:
                    temp_dict_for_storing[grid_index_tuple].append(block)
                else:
                    temp_dict_for_storing[grid_index_tuple] = [block]
            print(
                "Number of parent blocks for this block model: "
                + str(len(temp_dict_for_storing))
            )
            reverse_grid_index.append(temp_dict_for_storing)

            # *************************************************************************************************

            # Converting from world coordinates
            block_centroids = bm.convert_to_block_coordinates(block_centroids)
            block_centroids = block_centroids + 0.5 * np.array(
                [x_res[i], y_res[i], z_res[i]]
            )
            # *************************************************************************************************
            # Brute-force method
            print("Calculating block extents...")

            for nn, useless_var in tqdm(
                enumerate(block_centroids),
                total=len(block_centroids),
                desc="Progress",
                ncols=100,
                ascii=True,
                position=0,
                leave=True,
            ):
                # print(len(extents[0]))
                # print(len(extents[1]))
                extents[i].append(
                    (
                        [
                            (block_centroids[nn] - block_sizes[nn] / 2).tolist(),
                            (block_centroids[nn] + block_sizes[nn] / 2).tolist(),
                        ]
                    )
                )

            # *************************************************************************************************
            # # Checks all attributes of block and then chooses the one with discrete values
            a_dict = bm.block_attributes.names
            for key in a_dict:
                checker = bm.block_attributes[key]
                if isinstance(checker[0], (str, int)):
                    selected_var = checker
                    var_collection[i] = selected_var
            i = i + 1

# To check if the extents are the same for both given block models, this
# is a vital assumption for the code to work as the new blocks we create will be need the same extents to compare.
# print(totallength_x_dimension[0],totallength_y_dimension[0],totallength_z_dimension[0])
# print(totallength_x_dimension[1],totallength_y_dimension[1],totallength_z_dimension[1])
if (
    totallength_x_dimension[0] != totallength_x_dimension[1]
    or totallength_y_dimension[0] != totallength_y_dimension[1]
    or totallength_z_dimension[0] != totallength_z_dimension[1]
):
    print("Please select block models with the same extents, try again!")
    time.sleep(3)
    sys.exit()
# Getting "number of blocks" and the coordinates of all those blocks
# in the subblock model created for subblock-subblock comparison
# ###################################################################################################################
x_for_created_subblock = fractions.gcd(
    smallest_sub_size_block1[0], smallest_sub_size_block2[0]
)
y_for_created_subblock = fractions.gcd(
    smallest_sub_size_block1[1], smallest_sub_size_block2[1]
)
z_for_created_subblock = fractions.gcd(
    smallest_sub_size_block1[2], smallest_sub_size_block2[2]
)
number_of_blocks_in_created_subblock_model = (total_volume_of_block) / (
    x_for_created_subblock * y_for_created_subblock * z_for_created_subblock
)

# This checks if coordinates given by the user dont have a crazy small GCD value,
# if the value is too small it will make an unbelieveably large number of subblocks
# which we can not handle, I have set the limit to 10 billion.
if number_of_blocks_in_created_subblock_model > 10000000000:
    print(
        "Please enter x y z coordinates which are similar to the other block, Try Again."
    )
    time.sleep(3)
    sys.exit()

new_subblock_count_x_direction = totallength_x_dimension[0] / x_for_created_subblock
new_subblock_count_y_direction = totallength_y_dimension[0] / y_for_created_subblock
new_subblock_count_z_direction = totallength_z_dimension[0] / z_for_created_subblock

new_x_centroid_coordinate = np.linspace(
    (x_for_created_subblock / 2),
    (
        (new_subblock_count_x_direction * x_for_created_subblock)
        + x_for_created_subblock / 2
    ),
    int(new_subblock_count_x_direction),
    endpoint=False,
)

new_y_centroid_coordinate = np.linspace(
    (y_for_created_subblock / 2),
    (
        (new_subblock_count_y_direction * y_for_created_subblock)
        + y_for_created_subblock / 2
    ),
    int(new_subblock_count_y_direction),
    endpoint=False,
)

new_z_centroid_coordinate = np.linspace(
    (z_for_created_subblock / 2),
    (
        (new_subblock_count_z_direction * z_for_created_subblock)
        + z_for_created_subblock / 2
    ),
    int(new_subblock_count_z_direction),
    endpoint=False,
)


all_new_x_coordinates, all_new_y_coordinates, all_new_z_coordinates = np.meshgrid(
    new_x_centroid_coordinate,
    new_y_centroid_coordinate,
    new_z_centroid_coordinate,
    indexing="ij",
)

new_block_centroids = np.column_stack(
    (
        all_new_x_coordinates.flatten(),
        all_new_y_coordinates.flatten(),
        all_new_z_coordinates.flatten(),
    )
)


# ###################################################################################################################


print(1 * "\n")
print("Number of centroids that will be compared: " + str(len(new_block_centroids)))
print(1 * "\n")
# In[9]:
block_model_index = 0
new_block_centroids_collection = []
if solidfilter == "Yes":
    print("Doing solid filtering, this may take a couple minutes")
    for block_model_index, real_block_model in enumerate(selection):
        with project.read(solid_location) as solid:
            facets = solid.facets
            facet_points = solid.points

        x_Resolution = x_res[block_model_index]
        y_Resolution = y_res[block_model_index]
        z_Resolution = z_res[block_model_index]

        with project.edit(real_block_model) as bm:
            facet_points = bm.convert_to_block_coordinates(facet_points)
            facet_points = facet_points + 0.5 * np.array(
                [x_Resolution, y_Resolution, z_Resolution]
            )

        mesh = Trimesh(facet_points, facets, validate=True, use_embree=False)
        ray = ray_triangle.RayMeshIntersector(mesh)
        blocks_inside_solid = np.where(contains_points(ray, new_block_centroids))[0]
        blocks_inside_solid = new_block_centroids[blocks_inside_solid]

        new_block_centroids = blocks_inside_solid
        new_block_centroids_collection.append(new_block_centroids)
    comparison = new_block_centroids_collection[0] == new_block_centroids_collection[1]
    equal_arrays = comparison.all()
    if equal_arrays:
        print("Found all blocks inside solid!")
    # print(len(new_block_centroids_collection[0]), len(
    #     new_block_centroids_collection[1]))
    print(1 * "\n")
    print(
        "Number of new centroids that will be compared after solid restriction: "
        + str(len(new_block_centroids))
    )
    print(1 * "\n")


# In[10]:


# In[11]:


# SUB-BLOCK TO SUB-BLOCK COMPARISON
created_centroid_pos_in_orignal_block = [[] for _ in range(M)]
domains_of_created_block_centroids = [[] for _ in range(M)]
lengths_of_subblock_indices_for_orignal_block = [[] for _ in range(M)]
subblock_not_in_limits = []
subblock_exists_for_orignal_block = 0
outside_count_created_block = 0
string_not_found = 0
check = 0
block_model_index = 0
pointnotfound_in_indices_givenbygridindex = []
outside_indices_created_block = []

for block_model_index, item in enumerate(selection):
    # print(block_model_index)
    # print((domains_of_created_block_centroids[0]))
    # print((domains_of_created_block_centroids[1]))
    selected_model = item
    print(item.name)
    if item.is_a(DenseBlockModel) or item.is_a(SubblockedBlockModel):
        with project.edit(selected_model) as bm:
            for created_block_crawler, created_block_value in tqdm(
                enumerate(new_block_centroids),
                total=len(new_block_centroids),
                desc="Progress",
                ncols=100,
                ascii=True,
                position=0,
                leave=True,
            ):
                index_x_of_created_centroid = math.floor(
                    created_block_value[0] / x_res[block_model_index]
                )
                index_y_of_created_centroid = math.floor(
                    created_block_value[1] / y_res[block_model_index]
                )
                index_z_of_created_centroid = math.floor(
                    created_block_value[2] / z_res[block_model_index]
                )

                subblock_indices_for_orignal_block = reverse_grid_index[
                    block_model_index
                ].get(
                    (
                        index_x_of_created_centroid,
                        index_y_of_created_centroid,
                        index_z_of_created_centroid,
                    )
                )

                if (subblock_indices_for_orignal_block) is not None:
                    subblock_exists_for_orignal_block += 1
                    for subblock_crawler in subblock_indices_for_orignal_block:
                        check += 1
                        if (
                            (
                                extents[block_model_index][subblock_crawler][0][0]
                                <= created_block_value[0]
                                <= extents[block_model_index][subblock_crawler][1][0]
                            )
                            and (
                                extents[block_model_index][subblock_crawler][0][1]
                                <= created_block_value[1]
                                <= extents[block_model_index][subblock_crawler][1][1]
                            )
                            and (
                                extents[block_model_index][subblock_crawler][0][2]
                                <= created_block_value[2]
                                <= extents[block_model_index][subblock_crawler][1][2]
                            )
                        ):
                            check = 0
                            created_centroid_pos_in_orignal_block[
                                block_model_index
                            ].append(subblock_crawler)
                            # print(block_model_index)
                            domains_of_created_block_centroids[
                                block_model_index
                            ].append(
                                var_collection[block_model_index][subblock_crawler]
                            )

                            # print(str(len(domains_of_created_block_centroids[1])) +"," + str(created_block_crawler))
                            break
                        elif check == len(subblock_indices_for_orignal_block):
                            check = 0
                            pointnotfound_in_indices_givenbygridindex.append(
                                created_block_crawler
                            )
                else:
                    subblock_not_in_limits.append(created_block_crawler)

subblock_not_in_limits = list(set(subblock_not_in_limits))


# In[12]:
print(pointnotfound_in_indices_givenbygridindex)

print("Number of blocks not in limits: " + str(len(subblock_not_in_limits)))

print(1 * "\n")
# In[13]:


df3 = pd.DataFrame()
gandu0 = list(domains_of_created_block_centroids[0])
gandu1 = list(domains_of_created_block_centroids[1])
df3["sub0"] = pd.Series(gandu0)
df3["sub1"] = pd.Series(gandu1)

points_that_match = []
points_that_dont_match = []
for points_index, (x, y) in enumerate(zip(gandu0, gandu1)):
    if x == y:
        points_that_match.append(points_index)
    else:
        points_that_dont_match.append(points_index)

print(1 * "\n")
print(
    "Percenatge of space matching: "
    + str(100 * len(points_that_match) / len(gandu0))
    + " %"
)
# print("Percenatge of space not matching: "+str(100*len(points_that_dont_match) / len(gandu0))+" %")
print(1 * "\n")


# In[18]:


print(block_model_names[0])
print(df3["sub0"].value_counts())


print(1 * "\n")
print(block_model_names[1])
print(df3["sub1"].value_counts())
print(1 * "\n")


while True:
    number_to_restrict = input(
        "Insert N to see a confusion matrix of top N domains (Confusion matrix including all domains will be stored as Entire_Matrix.png): "
    )
    try:
        number_to_restrict = int(number_to_restrict)
        if (
            number_to_restrict < 0
        ):  # if not a positive int print message and ask for input again
            print("Sorry, input must be a positive integer, try again")
            continue
        break
    except ValueError:
        print("That's not an integer, try again!")

# Feature to display first N elemnts only on confusion matrix

sub0_domains_not_needed, sub0_domain_counts = np.unique(gandu0, return_counts=True)
sub0_values = np.sort(np.asarray((sub0_domains_not_needed, sub0_domain_counts)).T)
count_sort_ind = np.argsort(-sub0_domain_counts)
sub0_domains_not_needed = list(
    sub0_domains_not_needed[count_sort_ind[number_to_restrict:]]
)

sub1_domains_not_needed, sub1_domain_counts = np.unique(gandu1, return_counts=True)
sub1_values = np.sort(np.asarray((sub1_domains_not_needed, sub1_domain_counts)).T)
count_sort_ind = np.argsort(-sub1_domain_counts)
sub1_domains_not_needed = list(
    sub1_domains_not_needed[count_sort_ind[number_to_restrict:]]
)

df3["sub0_edited"] = pd.Series(gandu0)
df3["sub0_edited"] = df3["sub0_edited"].replace(sub0_domains_not_needed, "others")
df3["sub1_edited"] = pd.Series(gandu1)
df3["sub1_edited"] = df3["sub1_edited"].replace(sub1_domains_not_needed, "others")


point_confusion_matrix_for_sub = pd.crosstab(
    df3["sub0_edited"],
    df3["sub1_edited"],
    rownames=[block_model_names[0]],
    colnames=[block_model_names[1]],
)
point_confusion_matrix_for_sub = pd.DataFrame(point_confusion_matrix_for_sub)

mt = cm.figure(0)
gn = sns.heatmap(
    (point_confusion_matrix_for_sub) / (np.sum(point_confusion_matrix_for_sub)),
    cbar_kws={},
    annot=True,
    fmt=".2%",
    cmap="rocket_r",
    cbar=False,
    xticklabels=True,
    yticklabels=True,
)

# jellyfish.jaro_distance( gandu0, gandu1)
# difflib.SequenceMatcher(None, gandu0, gandu1).ratio()
cm.show()


# In[16]:


# CONFUSION MATRIX FOR SUB TO SUB COMPARISON


point_confusion_matrix_for_sub = pd.crosstab(
    df3["sub0"],
    df3["sub1"],
    rownames=[block_model_names[0]],
    colnames=[block_model_names[1]],
)
point_confusion_matrix_for_sub = pd.DataFrame(point_confusion_matrix_for_sub)

mt = cm.figure(0)
gn = sns.heatmap(
    (point_confusion_matrix_for_sub) / (np.sum(point_confusion_matrix_for_sub)),
    cbar_kws={},
    annot=True,
    fmt=".2%",
    cmap="rocket_r",
    cbar=False,
    xticklabels=True,
    yticklabels=True,
)

# jellyfish.jaro_distance( gandu0, gandu1)
# difflib.SequenceMatcher(None, gandu0, gandu1).ratio()
# cm.show()
mt.set_size_inches(22, 22)
mt.savefig("Entire_Matrix.png", dpi=100)
# Uncomment the lines below to generate a report.
# print(
#     metrics.classification_report(
#         df["Points Domain"], df["Block Domains"], labels=colour_names, zero_division=1
#     )
# # )
