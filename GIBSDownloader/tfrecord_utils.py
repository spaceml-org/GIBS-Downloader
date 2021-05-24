import os
import glob

try:
    import tensorflow as tf
except ImportError as e:
    raise Exception("Missing TensorFlow. Install with: pip install tensorflow==2.4.0")

from GIBSDownloader.coordinate_utils import Rectangle, Coordinate
from GIBSDownloader.file_metadata import TileMetadata

# Constants
MAX_FILE_SIZE = 100_000_000 # 100 MB recommended TFRecord file size

class TFRecordUtils():
    @classmethod
    def _bytes_feature(cls, value):
        """Returns a bytes_list from a string / byte."""
        if isinstance(value, type(tf.constant(0))):
            value = value.numpy()
        return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

    @classmethod
    def _float_feature(cls, value):
        """Returns a float_list from a float / double."""
        return tf.train.Feature(float_list=tf.train.FloatList(value=[value]))

    @classmethod
    def _int64_feature(cls, value):
        """Returns an int64_list from a bool / enum / int / uint."""
        return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

    @classmethod
    def image_example(cls, img_path, metadata):
        image_raw = open(img_path, 'rb').read()
        image_shape = tf.image.decode_png(image_raw).shape

        #print("Metdata info:", metadata.date, metadata.region.bl_coords.y, metadata.region.bl_coords.x, metadata.region.tr_coords.y, metadata.region.tr_coords.x)

        feature = {
            'date': TFRecordUtils._bytes_feature(bytes(metadata.date, 'utf-8')),
            'image_raw': TFRecordUtils._bytes_feature(image_raw),
            'width': TFRecordUtils._int64_feature(image_shape[0]),
            'height': TFRecordUtils._int64_feature(image_shape[1]),
            'bottom_left_lat': TFRecordUtils._float_feature(metadata.region.bl_coords.y),
            'bottom_left_long': TFRecordUtils._float_feature(metadata.region.bl_coords.x),
            'top_right_lat': TFRecordUtils._float_feature(metadata.region.tr_coords.y),
            'top_right_long': TFRecordUtils._float_feature(metadata.region.tr_coords.x),
        }

        return tf.train.Example(features=tf.train.Features(feature=feature))
    
    @classmethod
    def write_to_tfrecords(cls, input_path, output_path, name, img_format):
        files = [f for f in glob.glob(input_path + "**/*.{}".format(img_format), recursive=True)]
        count = 0
        version = 0
        while(count < len(files)):
            total_file_size = 0
            with tf.io.TFRecordWriter("{path}{name}_tf-{v}.tfrecord".format(path=output_path, name=name, v='%.3d' % (version))) as writer:
                while(total_file_size < MAX_FILE_SIZE and count < len(files)):    
                    filename = files[count]
                    metadata = TileMetadata(filename)
                    total_file_size += os.path.getsize(filename)
                    tf_example = TFRecordUtils.image_example(filename, metadata)
                    writer.write(tf_example.SerializeToString())
                    count += 1
            version += 1