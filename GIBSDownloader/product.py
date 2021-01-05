from enum import Enum

class Product(Enum):
    viirs = 'viirs'
    modis = 'modis'

    def __str__(self):
        if self == Product.viirs:
            return "VIIRS_SNPP_CorrectedReflectance_TrueColor"
        elif self == Product.modis:
            return "MODIS_Terra_CorrectedReflectance_TrueColor"

    def get_short_name(self):
        return self.value