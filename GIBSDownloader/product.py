from enum import Enum

class Product(Enum):
    viirs = 'viirs'
    modis = 'modis'

    def __str__(self):
        return self.value

    def get_long_name(self):
        if self == Product.viirs:
            return "VIIRS_SNPP_CorrectedReflectance_TrueColor"
        elif self == Product.modis:
            return "MODIS_Terra_CorrectedReflectance_TrueColor"