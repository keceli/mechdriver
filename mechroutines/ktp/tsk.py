""" Tasks for kTPDriver
"""

import os
import ioformat
import mess_io
import chemkin_io
import autorun
import ratefit
from mechlib import filesys
from mechlib.amech_io import writer
from mechlib.amech_io import output_path
from mechlib.amech_io import printer as ioprinter
from mechroutines.models.typ import use_well_extension
from mechroutines.ktp.rates import make_header_str
from mechroutines.ktp.rates import make_global_etrans_str
from mechroutines.ktp.rates import make_pes_mess_str
from mechroutines.ktp._multipes import obtain_multipes_rxn_ktp_dct


def write_messrate_task(pesgrp_num, pes_inf, rxn_lst,
                        tsk_key_dct, pes_param_dct,
                        spc_dct,
                        thy_dct, pes_model_dct, spc_model_dct,
                        unstab_chnls, label_dct,
                        rate_paths_dct, run_prefix, save_prefix):
    """ Reads and processes all information in the save filesys for
        all species on the PES that are required for MESS rate calculations,
        as specified by the model dictionaries built from user input.

        :param pes_idx:
        :type pes_idx: int
        :param rxn_lst:
        :type rxn_lst:
        :param pes_model: model for PES conditions for rates from user input
        :type pes_model: str
        :param spc_model: model for partition fxns for rates from user input
        :type spc_model: str
        :param mess_path: path to write mess file (change since pfx given?)
    """

    _, pes_idx, _ = pes_inf

    pes_mod = tsk_key_dct['kin_model']
    spc_mod = tsk_key_dct['spc_model']

    pes_model_dct_i = pes_model_dct[pes_mod]
    spc_model_dct_i = spc_model_dct[spc_mod]

    # Write the MESS strings for all the PES channels
    rxn_chan_str, dats, hot_enes_dct = make_pes_mess_str(
        spc_dct, rxn_lst, pes_idx, pesgrp_num, unstab_chnls,
        run_prefix, save_prefix, label_dct,
        tsk_key_dct, pes_param_dct,
        thy_dct, pes_model_dct_i, spc_model_dct_i, spc_mod)

    # Write the strings for the MESS input file
    globkey_str = make_header_str(
        spc_dct, rxn_lst, pes_idx, pesgrp_num,
        pes_param_dct, hot_enes_dct, label_dct,
        pes_model_dct_i['rate_temps'],
        pes_model_dct_i['pressures'],
        tsk_key_dct['float_precision'])

    # Write the energy transfer section strings for MESS file
    etransfer = pes_model_dct_i['glob_etransfer']
    energy_trans_str = make_global_etrans_str(
        rxn_lst, spc_dct, etransfer)

    # Write base MESS input string into the RUN filesystem
    mess_inp_str = mess_io.writer.messrates_inp_str(
        globkey_str, rxn_chan_str,
        energy_trans_str=energy_trans_str, well_lump_str=None)

    base_mess_path = rate_paths_dct[pes_inf]['base']
    ioprinter.obj('line_plus')
    ioprinter.writing('MESS input file', base_mess_path)
    ioprinter.debug_message('MESS Input:\n\n'+mess_inp_str)
    autorun.write_input(
        base_mess_path, mess_inp_str,
        aux_dct=dats, input_name='mess.inp')

    # Write the second MESS string (well extended), if needed
    if use_well_extension(spc_dct, rxn_lst, pes_idx,
                          tsk_key_dct['use_well_extension']):

        print('User requested well extension scheme for rates...')

        # Run the base MESSRATE
        autorun.run_script(autorun.SCRIPT_DCT['messrate'], base_mess_path)

        # Write the well-extended MESSRATE file
        print('Reading the input and output from the base MESSRATE run...')
        inp_str = ioformat.read_file(base_mess_path, 'mess.inp')
        out_str = ioformat.read_file(base_mess_path, 'mess.out')
        aux_str = ioformat.read_file(base_mess_path, 'mess.aux')
        log_str = ioformat.read_file(base_mess_path, 'mess.log')

        print('Setting up the well-extended MESSRATE input...')
        wext_mess_inp_str = ratefit.fit.well_lumped_input_file(
            inp_str, out_str, aux_str, log_str,
            pes_model_dct_i['well_extension_pressure'],
            pes_model_dct_i['well_extension_temp'])

        wext_mess_path = rate_paths_dct[pes_inf]['wext']
        ioprinter.obj('line_plus')
        ioprinter.writing('MESS input file', base_mess_path)
        ioprinter.debug_message('MESS Input:\n\n'+mess_inp_str)
        autorun.write_input(
            wext_mess_path, wext_mess_inp_str,
            aux_dct=dats, input_name='mess.inp')


def run_messrate_task(rate_paths_dct, pes_inf):
    """ Run the MESSRATE input file.

        First tries to run a well-extended file, then tries to
        run the base file if it exists.

        Need an overwrite task
    """
    path_dct = rate_paths_dct[pes_inf]
    for typ in ('wext', 'base'):
        path = path_dct[typ]
        mess_inp = os.path.join(path, 'mess.inp')
        mess_out = os.path.join(path, 'mess.out')
        if os.path.exists(mess_inp) and not os.path.exists(mess_out):
            ioprinter.obj('vspace')
            ioprinter.obj('line_dash')
            ioprinter.info_message(f'Found MESS input file at {path}')
            ioprinter.running('MESS input file')
            autorun.run_script(autorun.SCRIPT_DCT['messrate'], path)
            break


def run_fits_task(pes_grp_rlst, pes_param_dct, rate_paths_dct, mdriver_path,
                  label_dct, pes_mod_dct, spc_mod_dct, thy_dct,
                  tsk_key_dct):
    """ Run the fits and potentially

        assume that the rate_paths_dct will come in with all PESs in group
    """

    # Combine all PESs into a string for writing the CKIN file
    pes_strs = ()
    for pes_inf in pes_grp_rlst.keys():
        _inf = (pes_inf[0], str(pes_inf[1]+1), str(pes_inf[2]+1))
        pes_strs += ('_'.join(_inf),)
    tot_fml = '-'.join(pes_strs)

    # Get the model and sort info from tsk key dct
    pes_mod = tsk_key_dct['kin_model']
    spc_mod = tsk_key_dct['spc_model']
    sort_info_lst = filesys.mincnf.sort_info_lst(tsk_key_dct['sort'], thy_dct)

    ioprinter.obj('vspace')
    ioprinter.obj('line_dash')

    # Obtain the rate constants from the MESS files
    ioprinter.info_message(
        'Reading Rate Constants from MESS outputs', newline=1)
    rxn_ktp_dct = obtain_multipes_rxn_ktp_dct(
        rate_paths_dct, pes_param_dct,
        label_dct, pes_mod_dct, pes_mod)

    # Fit the rate constants
    ioprinter.info_message(
        'Fitting Rate Constants for PES to Functional Forms', newline=1)
    ratefit_dct = pes_mod_dct[pes_mod]['rate_fit']
    rxn_param_dct, rxn_err_dct = ratefit.fit.fit_rxn_ktp_dct(
        rxn_ktp_dct,
        ratefit_dct['fit_method'],
        pdep_dct=ratefit_dct['pdep_fit'],
        arrfit_dct=ratefit_dct['arrfit_fit'],
        chebfit_dct=ratefit_dct['chebfit_fit'],
        troefit_dct=ratefit_dct['troefit_fit'],
    )

    # Write the reactions block header, which contains model info
    rxn_block_cmt = writer.ckin.model_header(
        (spc_mod,), spc_mod_dct,
        sort_info_lst=sort_info_lst,
        refscheme=pes_mod_dct[pes_mod]['therm_fit']['ref_scheme'])

    # Get the comments dct and write the Chemkin string
    rxn_cmts_dct = chemkin_io.writer.comments.get_rxn_cmts_dct(
        rxn_err_dct=rxn_err_dct, rxn_block_cmt=rxn_block_cmt)
    ckin_str = chemkin_io.writer.mechanism.write_chemkin_file(
        rxn_param_dct=rxn_param_dct, rxn_cmts_dct=rxn_cmts_dct)

    # Write the file
    ckin_path = output_path('CKIN', prefix=mdriver_path)
    ckin_filename = f'{tot_fml}.ckin'
    ioformat.pathtools.write_file(ckin_str, ckin_path, ckin_filename)
