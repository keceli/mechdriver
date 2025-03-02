"""
Executes the automation part of 1DMin
"""

from mechlib.amech_io import printer as ioprinter
from mechroutines.trans._routines import run_onedmin
from mechroutines.trans._routines import build_transport_file


def run_tsk(tsk, spc_queue,
            spc_dct,
            thy_dct, etrans_keyword_dct,
            run_prefix, save_prefix):
    """ Run the task
    """

    # Print the head of the task
    ioprinter.obj('vspace')
    ioprinter.obj('line_dash')
    ioprinter.info_message('Task:', tsk, newline=1)
    ioprinter.info_message('Options for transport task:', newline=1)

    for key, val in etrans_keyword_dct.items():
        ioprinter.info_message(f'{key} = {val}')

    if tsk == 'onedmin':
        ioprinter.obj('vspace')
        ioprinter.obj('line_dash')
        ioprinter.info_message(
            'Obtaining LJ-Params using OneDMin', newline=1)
        for spc_name, _ in spc_queue:
            run_onedmin(spc_name,
                        spc_dct, thy_dct, etrans_keyword_dct,
                        run_prefix, save_prefix)
    elif tsk == 'write_transport':
        ioprinter.obj('vspace')
        ioprinter.obj('line_dash')
        ioprinter.info_message(
            'Writing the CHEMKIN transport file', newline=1)
        build_transport_file(spc_queue,
                             spc_dct, thy_dct, etrans_keyword_dct,
                             save_prefix)
