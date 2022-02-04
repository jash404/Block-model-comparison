from mapteksdk.project import Project
from mapteksdk.data import SubblockedBlockModel
from numpy import ndarray
# Block model 0 
#
#    2  +-------+-------+---------------+
#       |       |       |               |
#    1  |   o   |   o   |               |
#       |       |       |               |
#    0  +-------O-------+       o       |      0 = block coordinates origin.
#       |               |               |
#   -1  |       o       |               |
#       |               |               |
#   -2  +---------------+---------------+
#      -2       0       2       4       6
# Block model 1 
#
#    2  +-------+-------+---------------+
#       |       |       |               |
#    1  |       |       |       o       |
#       |       |       |               |
#    0  |   o   O   o   +-------+-------+     0 = block coordinates origin.
#       |       |       |       |       |
#   -1  |       |       |   o   |   o   |
#       |       |       |       |       |
#   -2  +-------+-------+-------+-------+
#      -2       0       2       4       6
centroids = [
    # Block model 0
    [[0, -1, 0],
     [-1, 1, 0], 
     [1, 1, 0],
     [4, 0, 0]],
    # Block model 1 
    [[-1, 0, 0],
     [1, 0, 0],
     [3, -1, 0],
     [5, -1, 0],
     [4, 1, 0]] 
    ]
sizes = [
    # Block model 0 
    [[4, 2, 4],
     [2, 2, 4], 
     [2, 2, 4],
     [4, 4, 4]],
    # Block model 1
    [[2, 4, 4],
     [2, 4, 4],
     [2, 2, 4],
     [2, 2, 4],
     [4, 2, 4]]
    ]
block_model_paths = ["blockmodels/subblockmodel_" + str(i) for i in range(len(centroids))]
project = Project()
create_block_models = False
if create_block_models:
    for path, c, s in zip(block_model_paths, centroids, sizes):
        with project.new(path, SubblockedBlockModel(
                x_count=2, y_count=1, z_count=1, x_res=4, y_res=4, z_res=4
                )) as new_blocks:
            new_blocks.add_subblocks(c, s)
for path in block_model_paths:
    print("Details for ", path)
    with project.read(path) as bmR:
        #print("  Block count", bmR.block_count)
        #print("  Block resolution", bmR.block_resolution)
        #print("  Block centroids", bmR.block_centroids)
        #print("  Row count", bmR.row_count)
        #print("  Column count", bmR.column_count)
        #
        # print("  Slice count", bmR.slice_count)
        print("  Block index to grid index")
        block_to_grid_index = bmR.block_to_grid_index
        for block_index, grid_index in enumerate(block_to_grid_index):
            print(block_index, grid_index)
        # The block index to grid looks like this, for example for block model 0,
        # so for any subblock we can now the parent grid block index.
        #
        #   block     grid 
        #   0       (0,0,0)
        #   1       (0,0,0)  
        #   2       (0,0,0)  
        #   3       (1,0,0)  
        #   4       (1,0,0)  
        # What we want is for any parent grid block index, look up the sub
        # blocks it contains. A dictionary like this would work.
        #
        #  (0,0,0) --> [0, 1, 2]
        #  (1,0,0) --> [3, 4]
        # Build the dictionary.
        grid_index_to_block = {}
        for block, grid_index in enumerate(block_to_grid_index):
            # We want to use the grid_index as the dictionary key. It needs to
            # be converted to a tuple which can be hashed.
            # Also, the grid_index is returned from the SDK as a float array
            # which seems odd. So convert to an integer array as well. 
            grid_index_tuple = tuple(grid_index.astype(int))
            if grid_index_tuple in grid_index_to_block:
                grid_index_to_block[grid_index_tuple].append(block)
            else:
                grid_index_to_block[grid_index_tuple] = [block]
        print(grid_index_to_block)            
        
