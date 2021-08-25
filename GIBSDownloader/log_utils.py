import io
import logging

def init_log(log, logfile):
    """
    Adds a file handler to the logger to log all output to the file
    
    Parameters:
        logfile (str): path to file to output log
        mode (str): mode to open the handler file ('w' or 'a')
    """
    f_handler = logging.FileHandler(logfile)
    formatter = logging.Formatter('%(asctime)s : %(name)s : %(message)s')
    f_handler.setFormatter(formatter)
    f_handler.setLevel(logging.DEBUG)
    log.addHandler(f_handler)


class TqdmToLogger(io.StringIO):
    """
        Output stream for TQDM which will output to logger module instead of
        the StdOut.

        Solution and code proposed by user @ddofborg
        https://github.com/tqdm/tqdm/issues/313
    """
    logger = None
    level = None
    buf = ''
    def __init__(self,logger,level=None):
        super(TqdmToLogger, self).__init__()
        self.logger = logger
        self.level = level or logging.INFO
    def write(self,buf):
        self.buf = buf.strip('\r\n\t ')
    def flush(self):
        self.logger.log(self.level, self.buf)