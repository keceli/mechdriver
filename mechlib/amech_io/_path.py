""" Library to build specifically formatted directory paths for
    various calculations conducted by MechDriver.
"""

import os
import random
import autofile
import automol
from mechanalyzer.inf import spc as sinfo


# Set paths to MESS jobs
def rate_paths(pes_dct, run_prefix):
    """ Set up the path for saveing the input and output of
        MESSRATE calculations

        Run different types of directories (1 PES)
            - fml-base: Standard base rate calculations (use idx)
            - fml-wext: Well-Extended base calculations (use 10*idx)
    """

    rate_path_dct = {}
    for pes_inf in pes_dct:
        pes_fml, pes_idx, subpes_idx = pes_inf

        _pes_str = f'{pes_fml}_{str(pes_idx+1)}_{str(subpes_idx+1)}'
        # idx1 = f'{pes_idx}-{subpes_idx}-BASE'
        # idx2 = f'{pes_idx}-{subpes_idx}-WEXT'
        idx1 = int(f'{pes_idx}{subpes_idx}0')
        idx2 = int(f'{pes_idx}{subpes_idx}1')
        rate_path_dct[pes_inf] = {
            'base': job_path(
                run_prefix, 'MESS', 'RATE', _pes_str, locs_idx=idx1),
            'wext': job_path(
                run_prefix, 'MESS', 'RATE', _pes_str, locs_idx=idx2)
        }

    return rate_path_dct


def thermo_paths(spc_dct, spc_locs_dct, spc_mods, run_prefix):
    """ Set up the path for saving the pf input and output.
        Placed in a MESSPF, NASA dirs high in run filesys.
    """

    thm_path_dct = {}
    for spc_name in spc_locs_dct:
        spc_thm_path_dct = {}
        spc_info = sinfo.from_dct(spc_dct[spc_name])
        spc_formula = automol.inchi.formula_string(spc_info[0])
        thm_prefix = [spc_formula, automol.inchi.inchi_key(spc_info[0])]
        spc_locs_lst = spc_locs_dct[spc_name]
        for sidx, spc_locs in enumerate(spc_locs_lst, start=1):
            spc_mod_thm_path_dct = {}
            for midx, mod in enumerate(spc_mods):
                idx = sidx * 10 + midx
                spc_mod_thm_path_dct[mod] = (
                    job_path(
                        run_prefix, 'MESS', 'PF',
                        thm_prefix, locs_idx=idx),
                    job_path(
                        run_prefix, 'THERM', 'NASA',
                        thm_prefix, locs_idx=idx)
                )
            spc_mod_thm_path_dct['mod_total'] = (
                job_path(
                    run_prefix, 'MESS', 'PF',
                    thm_prefix, locs_idx=sidx),
                job_path(
                    run_prefix, 'THERM', 'NASA',
                    thm_prefix, locs_idx=sidx)
            )
            spc_thm_path_dct[tuple(spc_locs)] = spc_mod_thm_path_dct
        spc_thm_path_dct['spc_total'] = (
            job_path(
                run_prefix, 'MESS', 'PF',
                thm_prefix, locs_idx=0),
            job_path(
                run_prefix, 'THERM', 'NASA',
                thm_prefix, locs_idx=0)
        )
        thm_path_dct[spc_name] = spc_thm_path_dct
    return thm_path_dct


def output_path(dat, make_path=True, print_path=False, prefix=None):
    """ Create the path for sub-directories locatted in the run directory
        where the MechDriver calculation was launched. These sub-directories
        are used to store various useful output from the MechDriver process.

        :param make_path: physically create directory for path during function
        :type make_path: bool
        :param print_path: print the created path to the screen
        :type print_path: bool
        :param prefix: prefix for directory to be built
        :type prefix: str
        :rtype: str
    """

    # Initialize the path
    starting_path = prefix if prefix is not None else os.getcwd()
    path = os.path.join(starting_path, dat)

    # Make and print the path, if requested
    if make_path:
        if not os.path.exists(path):
            os.makedirs(path)
    if print_path:
        print(f'output path for {dat}: {path}')

    return path


def job_path(prefix, prog, job, fml,
             locs_idx=None, make_path=True, print_path=False):
    """ Create the path for various types of calculations for
        a given species or PES.

        :param prefix: root prefix to run/save filesyste,
        :type prefix: str
        :param prog: name of the program(s) called in the job
        :type prog: str
        :param fml: stoichiometry of the species/PES associate with job
        :fml type: str
        :param locs_idx: number denoting final layer of filesys for job
        :type locs_idx: int
        :param make_path: physically create directory for path during function
        :type make_path: bool
        :param print_path: print the created path to the screen
        :type print_path: bool
        :rtype: str
    """

    # Initialize the build object
    prog_prefix = os.path.join(prefix, prog)
    bld_fs = autofile.fs.build(prog_prefix)

    # Determine the index for the locs if not provided
    if locs_idx is not None:
        assert isinstance(locs_idx, int), (
            f'locs idx {locs_idx} is not an integer'
        )
    else:
        locs_idx = random.randint(0, 9999999)

    if not isinstance(fml, str):
        fml = '-'.join(fml)

    # Build the path
    bld_locs = [job, fml, locs_idx]
    bld_path = bld_fs[-1].path(bld_locs)

    # Make and print the path, if requested
    if make_path:
        bld_fs[-1].create([job, fml, locs_idx])
    if print_path:
        print(f'Path for {prog}/{job} Job:')
        print(bld_path)

    return bld_path
