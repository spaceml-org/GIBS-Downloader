import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

c_handler = logging.StreamHandler()
formatter = logging.Formatter('%(name)s : %(message)s')
c_handler.setFormatter(formatter)
c_handler.setLevel(logging.INFO)
log.addHandler(c_handler)