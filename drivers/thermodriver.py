""" Driver for thermochemistry evaluations including
    heats-of-formation and NASA polynomials describing
    thermodynamic quantities: Enthalpy, Entropy, Gibbs

    Main Loop of Driver:
        (1) PES or SPC list

    Main Workflow:
        (1) Write MESS:
            (1) Collate and process data from the SAVE filesystem
            (2) Format and write data into MESSPF input file
        (2) Run MESS:
            (1) Run MESS file to obtain partition functions
        (3) Run fits:
            (1) Read all partition functions from MESS output
            (2) Run PACC+ThermP to fit thermo NASA polynomials
            (3) Write functional forms to mechanism file
"""

from mechroutines.thermo import tsk as thermo_tasks
from mechlib import filesys
from mechlib.amech_io import writer
from mechlib.amech_io import parser
from mechlib.amech_io import printer as ioprinter
from mechlib.amech_io import thermo_paths
from mechlib.reaction import split_unstable_full


def run(pes_rlst, spc_rlst,
        therm_tsk_lst,
        pes_mod_dct, spc_mod_dct,
        spc_dct, thy_dct,
        run_prefix, save_prefix, mdriver_path):
    """ Executes all thermochemistry tasks.

        :param pes_rlst: species from PESs to run
            [(PES formula, PES idx, SUP-PES idx)
            (CHANNEL idx, (REACS, PRODS))
        :type pes_rlst: tuple(dict[str: dict])
        :param spc_rlst: lst of species to run
        :type spc_rlst: tuple(dict[str: dict])
        :param es_tsk_lst: list of the electronic structure tasks
        :type es_tsk_lst: tuple(tuple(str, str, dict))
        :param spc_dct: species information
        :type spc_dct: dict[str:dict]
        :param glob_dct: global information for all species
        :type glob_dct: dict[str: dict]
        :param thy_dct: all of the theory information
        :type thy_dct: dict[str:dict]
        :param run_prefix: root-path to the run-filesystem
        :type run_prefix: str
        :param save_prefix: root-path to the save-filesystem
        :type save_prefix: str
        :param mdriver_path: path where mechdriver is running
        :type mdriver_path: str
    """

    # Print Header
    ioprinter.info_message('Calculating Thermochem:')
    ioprinter.runlst(
        list(spc_rlst.keys())[0],
        list(spc_rlst.values())[0])

    # ------------------------------------------------ #
    # PREPARE INFORMATION TO PASS TO THERMDRIVER TASKS #
    # ------------------------------------------------ #

    # Parse Tasks
    write_messpf_tsk = parser.run.extract_task('write_mess', therm_tsk_lst)
    run_messpf_tsk = parser.run.extract_task('run_mess', therm_tsk_lst)
    run_fit_tsk = parser.run.extract_task('run_fits', therm_tsk_lst)

    # Build a list of the species to calculate thermochem for loops below
    # and build the paths [(messpf, nasa)], models and levels for each spc
    cnf_range = write_messpf_tsk[-1]['cnf_range']
    sort_str = write_messpf_tsk[-1]['sort']
    spc_locs_dct, thm_paths_dct, sort_info_lst = _set_spc_queue(
        spc_mod_dct, pes_rlst, spc_rlst, spc_dct, thy_dct,
        save_prefix, run_prefix, cnf_range, sort_str)

    # ----------------------------------- #
    # RUN THE REQUESTED THERMDRIVER TASKS #
    # ----------------------------------- #

    # Write and Run MESSPF inputs to generate the partition functions
    if write_messpf_tsk is not None:
        thermo_tasks.write_messpf_task(
            write_messpf_tsk, spc_locs_dct, spc_dct,
            pes_mod_dct, spc_mod_dct,
            run_prefix, save_prefix, thm_paths_dct)

    # Run the MESSPF files that have been written
    if run_messpf_tsk is not None:
        thermo_tasks.run_messpf_task(
            run_messpf_tsk, spc_locs_dct, spc_dct,
            thm_paths_dct)

    # Use MESS partition functions to compute thermo quantities
    if run_fit_tsk is not None:

        ioprinter.nasa('header')
        spc_mods, pes_mod = parser.models.extract_models(run_fit_tsk)
        pes_mod_dct_i = pes_mod_dct[pes_mod]

        # Get the reference scheme and energies (ref in different place)
        ref_scheme = pes_mod_dct_i['therm_fit']['ref_scheme']
        ref_enes = pes_mod_dct_i['therm_fit']['ref_enes']
        spc_dct = thermo_tasks.get_heats_of_formation(
            spc_locs_dct, spc_dct, spc_mods, spc_mod_dct,
            ref_scheme, ref_enes, run_prefix, save_prefix)

        # This has to happen down here because the weights rely on
        # The heats of formation
        print('in run_fit_tsk for thermo_driver boltzmann')
        spc_dct = thermo_tasks.produce_boltzmann_weighted_conformers_pf(
            run_messpf_tsk, spc_locs_dct, spc_dct,
            thm_paths_dct)

        # Write the NASA polynomials in CHEMKIN format
        ckin_nasa_str_dct, ckin_path = thermo_tasks.nasa_polynomial_task(
            mdriver_path, spc_locs_dct, thm_paths_dct, spc_dct,
            spc_mod_dct, spc_mods, sort_info_lst, ref_scheme)

        for idx, nasa_str in ckin_nasa_str_dct.items():
            ioprinter.print_thermo(
                spc_dct, nasa_str,
                spc_locs_dct, idx, spc_mods[0])

            # Write all of the NASA polynomial strings
            writer.ckin.write_nasa_file(
                nasa_str, ckin_path, idx=idx)


def _set_spc_queue(
        spc_mod_dct, pes_rlst, spc_rlst,
        spc_dct, thy_dct, save_prefix, run_prefix,
        cnf_range='min', sort_str=None):
    """ Determine the list of species to do thermo on
    """
    spc_mods = list(spc_mod_dct.keys())  # hack
    spc_mod_dct_i = spc_mod_dct[spc_mods[0]]
    sort_info_lst = filesys.mincnf.sort_info_lst(sort_str, thy_dct)
    split_rlst = split_unstable_full(
        pes_rlst, spc_rlst, spc_dct, spc_mod_dct_i, save_prefix)
    spc_queue = parser.rlst.spc_queue(
        tuple(split_rlst.values())[0], 'SPC')
    spc_locs_dct = _set_spc_locs_dct(
        spc_queue, spc_dct, spc_mod_dct_i, run_prefix, save_prefix,
        cnf_range, sort_info_lst)
    thm_paths = thermo_paths(spc_dct, spc_locs_dct, spc_mods, run_prefix)
    return spc_locs_dct, thm_paths, sort_info_lst


def _set_spc_locs_dct(
        spc_queue, spc_dct, spc_mod_dct_i, run_prefix, save_prefix,
        cnf_range='min', sort_info_lst=None, saddle=False):
    """ get a dictionary of locs
    """
    spc_locs_dct = {}
    for spc_name in spc_queue:
        spc_locs_lst = filesys.models.get_spc_locs_lst(
            spc_dct[spc_name], spc_mod_dct_i,
            run_prefix, save_prefix, saddle=saddle,
            cnf_range=cnf_range, sort_info_lst=sort_info_lst)
        spc_locs_dct[spc_name] = spc_locs_lst
    return spc_locs_dct
