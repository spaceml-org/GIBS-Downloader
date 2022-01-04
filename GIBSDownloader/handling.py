from enum import Enum

class Handling(Enum):
    """
    Enum storing how to handle tiling images at their boundaries

    Values:
        complete_tile_shift: shift the tile so that includes the full tile width/height specified by the user
        include_incomplete_tile: do not shift the tiles
        discard_incomplete_tiles: throw away incomplete tiles
    """
    complete_tiles_shift = 'complete-tiles-shift'
    include_incomplete_tiles = 'include-incomplete-tiles'
    discard_incomplete_tiles = 'discard-incomplete-tiles'
    
    def __str__(self):
        return self.value