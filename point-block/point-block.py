#!/usr/bin/env python3.7
# coding: utf-8

# In[1]:


# Imports for the Maptek Python SDK and additional libraries.
import collections
import copy
import ctypes
import fractions
import math
import sys
import time
import json
from collections import defaultdict
from itertools import islice

import matplotlib as mpl
import matplotlib.colors as cc

# mpl.use('agg')
import matplotlib.pyplot as cm
import numpy as np
import pandas as pd
import seaborn as sns
from mapteksdk.data import (
    DenseBlockModel,
    GridSurface,
    NumericColourMap,
    SubblockedBlockModel,
    Surface,
    Text3D,
)
from mapteksdk.project import Project
from matplotlib.ticker import PercentFormatter
from matplotlib.widgets import Button, CheckButtons, RadioButtons
from sklearn import metrics
from sklearn.metrics import confusion_matrix
from tqdm import tqdm_gui
from tqdm.auto import tqdm, trange

cm.rcParams["font.family"] = ["Source Han Sans TW", "monospace"]
cm.rcParams["font.size"] = 14

# Connect to the currently running Maptek Project.
project = Project()
# project.mcp_instance.mcp_dict['PRODUCT_LOCATION_INFO']  # Report out which application it connected to (Optional)


# In[2]:


# Initialisation
selected_model = None
selected_var = ""
colours = ""
real_colours = []
vis = ""
# ****************Bool switches for certain features*****************************************************************
vis_compiler = False
point_checker = True
# ********************************************************************************************************************
names = []
df = pd.DataFrame()
objects_selected_in_project = project.get_selected()
last_opacity = 255

global length_of_selection
length_of_selection = len(objects_selected_in_project)
vis_collection = [0] * length_of_selection
var_collection = [0] * length_of_selection
index_map = [0] * length_of_selection
extents = [[] for _ in range(length_of_selection)]
# i tells you the index of the block_model
block_model_index = 0

for name_iterator in objects_selected_in_project:
    block_model_name = name_iterator.name
    if (
        name_iterator.is_a(DenseBlockModel) == False
        and name_iterator.is_a(SubblockedBlockModel) == False
    ):
        print("Please select a Block Model to compare, Try Again.")
        time.sleep(3)
        sys.exit()


if len(objects_selected_in_project) < 1:
    print("Please select a Block Model to compare, Try Again.")
    time.sleep(3)
    sys.exit()
elif len(objects_selected_in_project) > 1:
    print("Please select only one Block Model to compare with the points, Try Again")
    time.sleep(3)
    sys.exit()

point_location = input(
    "Put in the exact location of PointSet you want to compare (ex:samples/PointSet ) : "
)

# DATA GETTER

for item in objects_selected_in_project:
    print("The name of the Block Model you have selected: " + str(item.name))
    # Setting outer array back to 0, for new block
    nn = 0
    if item.is_a(DenseBlockModel) or item.is_a(SubblockedBlockModel):
        selected_model = item
        # Checker for point stuff
        if point_checker:
            # Getting all block details
            with project.edit(selected_model) as bm:

                block_sizes = bm.block_sizes
                block_centroids = bm.block_centroids
                b = bm.block_resolution
                x_res = float(b[0])
                y_res = float(b[1])
                z_res = float(b[2])

                x_count = bm.column_count
                y_count = bm.row_count
                z_count = bm.slice_count

                totallength_x_dimension = x_res * x_count
                totallength_y_dimension = y_res * y_count
                totallength_z_dimension = z_res * z_count

                index_map[block_model_index] = bm.block_to_grid_index
                # index_map[i] = index_map[i].tolist()
                number_of_parent_blocks = len(
                    np.unique(index_map[block_model_index], axis=0)
                )
                total_volume_of_block = number_of_parent_blocks * x_res * y_res * z_res

                # ****************************************************************
                # * This the better fast method.
                temp_dict_for_storing = {}
                for block, grid_index in tqdm(
                    enumerate(index_map[block_model_index]),
                    total=len(index_map[block_model_index]),
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
                reverse_grid_index = temp_dict_for_storing

                # **********************************************************************************************
                # Converting from world coordinates
                block_centroids = bm.convert_to_block_coordinates(block_centroids)
                block_centroids = block_centroids + 0.5 * np.array(
                    [x_res, y_res, z_res]
                )

                # Getting sample point data for point to block comparison

                with project.read(point_location) as points:
                    # SDK method
                    real_points = points.points
                    point_visibility = points.point_visibility
                    real_points = bm.convert_to_block_coordinates(real_points)
                    real_points = real_points + 0.5 * np.array([x_res, y_res, z_res])
                    point_collection = [0] * len(real_points)
                    point_domains_names = points.point_attributes.names
                    for dictionary in point_domains_names:
                        if (
                            json.loads(dictionary)["c"] == "Domain"
                            or json.loads(dictionary)["c"] == "domain"
                            or json.loads(dictionary)["c"] == "geocod"
                        ):
                            point_domain_dict = str(dictionary)
                    point_domains = points.point_attributes[point_domain_dict]

                # *************************************************************************************************
                # Brute-force method
                # ! Also np.round is needed for keeping the decimal place for extents in check,
                # ! if this is not done then it is more by a small value which leads to
                # ! leaving out certain points while check.
                # ! However np.round is quite slow.
                print("Calculating block extents....")

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
                    extents[block_model_index].append(
                        (
                            [
                                np.round(
                                    (block_centroids[nn] - block_sizes[nn] / 2), 6
                                ).tolist(),
                                np.round(
                                    (block_centroids[nn] + block_sizes[nn] / 2), 6
                                ).tolist(),
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
                        var_collection[block_model_index] = selected_var
                vis = bm.block_visibility
                vis_collection[block_model_index] = vis
                block_model_index = block_model_index + 1


#########################################################


# In[15]:


# unique_rows = np.unique(index_map[0], axis=0)
# print("Number of parent blocks:")
# print(len(unique_rows))


# In[17]:


# POINT TO BLOCK/SUB-BLOCK COMPARISON
dict_of_point_and_its_corresponding_block_location = {}
points_that_dont_match = []
points_that_match = []
domains_of_blocks = []
outside_count = 0
subblock_exists = 0
outside_indices = []
point_in_sublock = []
lengths_of_subblock_indices = []
number_of_checks_happening_per_block = []
samplepoints_crawler = 0
check = 0
pointnotfound_in_indices_givenbygridindex = []
with project.read(selected_model) as bm:
    for samplepoints_crawler, samplepoints_value in tqdm(
        enumerate(real_points),
        total=len(real_points),
        desc="Progress",
        ncols=100,
        ascii=True,
        position=0,
        leave=True,
    ):
        index_x_of_created_centroid = math.floor(samplepoints_value[0] / x_res)
        index_y_of_created_centroid = math.floor(samplepoints_value[1] / y_res)
        index_z_of_created_centroid = math.floor(samplepoints_value[2] / z_res)

        # if (0 <= c1 < x_count) and (0 <= c2 < y_count) and (0 <= c3 < z_count):
        subblock_indices = reverse_grid_index.get(
            (
                index_x_of_created_centroid,
                index_y_of_created_centroid,
                index_z_of_created_centroid,
            )
        )
        if (subblock_indices) is not None:
            subblock_exists += 1
            for subblock_indices_crawler in subblock_indices:
                check += 1
                if (
                    (
                        extents[0][subblock_indices_crawler][0][0]
                        <= samplepoints_value[0]
                        <= extents[0][subblock_indices_crawler][1][0]
                    )
                    and (
                        extents[0][subblock_indices_crawler][0][1]
                        <= samplepoints_value[1]
                        <= extents[0][subblock_indices_crawler][1][1]
                    )
                    and (
                        extents[0][subblock_indices_crawler][0][2]
                        <= samplepoints_value[2]
                        <= extents[0][subblock_indices_crawler][1][2]
                    )
                ):

                    number_of_checks_happening_per_block.append(
                        (check, samplepoints_crawler)
                    )
                    check = 0
                    point_in_sublock.append(subblock_indices_crawler)
                    dict_of_point_and_its_corresponding_block_location[
                        samplepoints_crawler
                    ] = subblock_indices_crawler
                    domains_of_blocks.append(selected_var[subblock_indices_crawler])
                    break
                elif check == len(subblock_indices):
                    check = 0
                    pointnotfound_in_indices_givenbygridindex.append(
                        samplepoints_crawler
                    )
        else:
            # print(c1, c2, c3)
            outside_count += 1
            outside_indices.append(samplepoints_crawler)
            continue


point_to_be_deleted_before_check = outside_indices
point_domains = [z.lower() for z in point_domains]
point_domains_wo_outliers = []
point_domains_wo_outliers = copy.deepcopy(point_domains)
# print(len(point_to_be_deleted_before_check))
# print((point_to_be_deleted_before_check)   )

point_domains_wo_outliers = np.delete(
    point_domains_wo_outliers, point_to_be_deleted_before_check
)

# This loop below is basically for finding how many blocks match or not, we are storing the indexes for
# getting their positions in the list where outsiders are already cut out


for points_index, (x, y) in enumerate(
    zip(point_domains_wo_outliers, domains_of_blocks)
):
    if x == y:
        points_that_match.append(points_index)
    else:
        points_that_dont_match.append(points_index)

# For getting positions of points which dont match with the blocks they are positioned in
point_pos_which_dont_match = copy.deepcopy(
    list(dict_of_point_and_its_corresponding_block_location.values())
)
# Deleting all values which are matching, hencing leaving us with the positions where there is no matching
point_pos_which_dont_match = np.delete(point_pos_which_dont_match, points_that_match)


print("*******************")
print("*******************")
print("Number of points which do not match: " + str(len(points_that_dont_match)))
print("Number of points which match:: " + str(len(points_that_match)))
print("**********************************************************")

# print(len(point_domains_wo_outliers))
# print(len(domains_of_blocks))
# print("Blocks found: " + str(subblock_exists))
print("Number of points which are outside the model: " + str(outside_count))
print("*******************")

# print(point_domains_wo_outliers[:20])
# print(domains_of_blocks)
print("*******************")
print(
    "points not found inside block indices given by grid_index and their total number:"
)
print(pointnotfound_in_indices_givenbygridindex)
print(len(pointnotfound_in_indices_givenbygridindex))


# In[49]:


# STATISTICAL REPORT
df2 = pd.DataFrame()

match_percentage = str(
    round(((len(points_that_match) * 100) / len(point_domains_wo_outliers)), 2)
)

print(
    "From "
    + str(len(point_domains_wo_outliers))
    + " points (excluding "
    + str((outside_count))
    + " outliers, which were outside the block model) "
    + str(len(points_that_match))
    + " points were in the same block with the same domain"
    + " hence having a match percentage of "
    + match_percentage
)

print("The number of unique points:" + str(len(point_domains_wo_outliers)))
print(
    "The number of unique blocks:"
    + str(len(set(list(dict_of_point_and_its_corresponding_block_location.values()))))
)

print(len(point_domains_wo_outliers))
print(len(domains_of_blocks))

df2["Points Domain"] = pd.Series(point_domains_wo_outliers)
df2["Block Domains"] = pd.Series(domains_of_blocks)

print(1 * "\n")
print("Domain distribution in SAMPLE:")

# This helps gets percentage for each domain, as requested by richard
(point_domain_names, domain_frequencies) = np.unique(
    point_domains_wo_outliers, return_counts=True
)
(block_domain_names, block_domain_frequencies) = np.unique(
    domains_of_blocks, return_counts=True
)


print(df2["Points Domain"].value_counts())
for x, y in zip(point_domain_names, domain_frequencies):
    print(
        str(x)
        + ": "
        + str(round((y * 100) / (len(point_domains_wo_outliers)), 2))
        + " %"
    )

print(1 * "\n")
print("Domain distribution in " + str(block_model_name) + ":")
print(df2["Block Domains"].value_counts())
for x, y in zip(block_domain_names, block_domain_frequencies):
    print(
        str(x)
        + ": "
        + str(round((y * 100) / (len(point_domains_wo_outliers)), 2))
        + " %"
    )


# In[12]:
blockfilter = "No"
print(1 * "\n")
blockfilter = input(
    "Do you want to only see the blocks and points where the PointSet is not matching with the Block Model (Yes/No): "
)


if (blockfilter == "Yes") or (blockfilter == "Y") or (blockfilter == "y"):
    blockfilter = "Yes"
    print(
        "A new container called Filtered_block_and_points contains the edited Model and Pointset"
    )
    time.sleep(3)

if blockfilter == "Yes":

    project.new_visual_container("/", "Filtered_block_and_points")
    filtered_block = project.copy_object(
        selected_model, "Filtered_block_and_points/Filtered_Block", overwrite=True
    )
    filtered_pointset = project.copy_object(
        point_location, "Filtered_block_and_points/Filtered_PointSet", overwrite=True
    )
    # Only show BLOCKS which dont match their domain
    block_array_of_visibility_created = []
    with project.edit(filtered_block) as bm:
        block_array_of_visibility = bm.block_visibility

        block_array_of_visibility_created = [False] * len(block_array_of_visibility)

        unique_blocks_which_contain_points_that_dont_match = set(
            point_pos_which_dont_match
        )

        for values in unique_blocks_which_contain_points_that_dont_match:
            block_array_of_visibility_created[values] = True
        bm.block_visibility = block_array_of_visibility_created

    # In[13]:

    # Only show POINTS which dont match their domain
    point_array_of_visibility_created = []
    with project.edit(filtered_pointset) as points:
        point_array_of_visibility = points.point_visibility
        point_array_of_visibility_created = [False] * len(point_array_of_visibility)
        point_array_of_visibility_created_wo_outliers = copy.deepcopy(
            point_array_of_visibility_created
        )
        # Eliminating outliers from visibilty array
        point_array_of_visibility_created_wo_outliers = np.delete(
            point_array_of_visibility_created_wo_outliers,
            point_to_be_deleted_before_check,
        )
        # Eliminating outliers from physical PointSet itself
        points.remove_points(point_to_be_deleted_before_check, update_immediately=True)
        points.save()
        for values1 in points_that_dont_match:
            point_array_of_visibility_created_wo_outliers[values1] = True
        points.point_visibility = point_array_of_visibility_created_wo_outliers


# In[14]:


# # Gets previous visibilty back
# with project.edit(point_location) as points:
#     with project.edit(selected_model) as bm:
#         bm.block_visibility = vis
#         points.point_visibility = point_visibility


# In[43]:

while True:
    print(1 * "\n")
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

sub0_domains_not_needed, sub0_domain_counts = np.unique(
    point_domains_wo_outliers, return_counts=True
)
sub0_values = np.sort(np.asarray((sub0_domains_not_needed, sub0_domain_counts)).T)
count_sort_ind = np.argsort(-sub0_domain_counts)
sub0_domains_not_needed = list(
    sub0_domains_not_needed[count_sort_ind[number_to_restrict:]]
)

sub1_domains_not_needed, sub1_domain_counts = np.unique(
    domains_of_blocks, return_counts=True
)
sub1_values = np.sort(np.asarray((sub1_domains_not_needed, sub1_domain_counts)).T)
count_sort_ind = np.argsort(-sub1_domain_counts)
sub1_domains_not_needed = list(
    sub1_domains_not_needed[count_sort_ind[number_to_restrict:]]
)

df2["point_domains_edited"] = pd.Series(point_domains_wo_outliers)
df2["point_domains_edited"] = df2["point_domains_edited"].replace(
    sub0_domains_not_needed, "others"
)
df2["block_domains_edited"] = pd.Series(domains_of_blocks)
df2["block_domains_edited"] = df2["block_domains_edited"].replace(
    sub1_domains_not_needed, "others"
)


# CONFUSION MATRIX FOR POINT TO BLOCK COMPARISON
point_confusion_matrix = pd.crosstab(
    df2["point_domains_edited"],
    df2["block_domains_edited"],
    rownames=["Points"],
    colnames=[block_model_name],
)
point_confusion_matrix = pd.DataFrame(point_confusion_matrix)

mt = cm.figure(0)
gn = sns.heatmap(
    (point_confusion_matrix) / (np.sum(point_confusion_matrix)),
    cbar_kws={},
    annot=True,
    fmt=".2%",
    cmap="rocket_r",
    cbar=False,
    xticklabels=True,
    yticklabels=True,
)

cm.show()
# Uncomment the lines below to generate a report.
# print(
#     metrics.classification_report(
#         df["Points Domain"], df["Block Domains"], labels=colour_names, zero_division=1
#     )
# )

# In[43]:


# CONFUSION MATRIX FOR POINT TO BLOCK COMPARISON
point_confusion_matrix = pd.crosstab(
    df2["Points Domain"],
    df2["Block Domains"],
    rownames=["Points"],
    colnames=[block_model_name],
)
point_confusion_matrix = pd.DataFrame(point_confusion_matrix)

mt = cm.figure(0)
gn = sns.heatmap(
    (point_confusion_matrix) / (np.sum(point_confusion_matrix)),
    cbar_kws={},
    annot=True,
    fmt=".2%",
    cmap="rocket_r",
    cbar=False,
    xticklabels=True,
    yticklabels=True,
)

mt.set_size_inches(22, 22)
mt.savefig("Entire_Matrix.png", dpi=100)
# Uncomment the lines below to generate a report.
# print(
#     metrics.classification_report(
#         df["Points Domain"], df["Block Domains"], labels=colour_names, zero_division=1
#     )
# )

input("Press enter to exit. ")
