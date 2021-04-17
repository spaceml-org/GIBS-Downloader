from enum import Enum

# Enum to decide how to handle images at boundaries
class Handling(Enum):
    complete_tiles_shift = 'complete-tiles-shift'
    include_incomplete_tiles = 'include-incomplete-tiles'
    discard_incomplete_tiles = 'discard-incomplete-tiles'
    
    def __str__(self):
        return self.value