"""
  Handle building the energy transfer section
"""

import automol
import mess_io
from mechanalyzer.inf import spc as sinfo
from mechlib.amech_io import printer as ioprinter


# FUNCTIONS TO WRITE THE ENERGY TRANSFER  STRINGS
def make_energy_transfer_strs(well_info, bath_info, etrans_dct):
    """ Writes the energy down (`Edown`) and collision frequency (`ColldFreq`)
        section strings for the MESS input.

    Makes the standard header and energy transfer sections
        for MESS input file
    """

    # Determine all of the energy transfer parameters
    ioprinter.info_message(
        '- Determining the masses...', newline=1)
    mass1, mass2 = mass_params(
        well_info, bath_info, etrans_dct)

    ioprinter.info_message(
        '- Determining the Lennard-Jones model parameters...', newline=1)
    sig1, eps1, sig2, eps2 = lj_params(
        well_info, bath_info, etrans_dct)

    ioprinter.info_message(
        '- Determining the energy-down transfer model parameters...',
        newline=1)
    exp_factor, exp_power, exp_cutoff = edown_params(
        well_info, bath_info, etrans_dct,
        ljpar=(sig1, eps1, mass1, mass2))

    # Write the Energy Transfer section string
    if all(val is not None
           for val in (sig1, sig2, eps1, eps2, exp_factor, exp_power)):
        edown_str = mess_io.writer.energy_down(
            exp_factor, exp_power, exp_cutoff)
        collid_freq_str = mess_io.writer.collision_frequency(
            eps1, eps2, sig1, sig2, mass1, mass2)
    else:
        # set defaults?
        edown_str, collid_freq_str = None, None

    return edown_str, collid_freq_str


# FUNCTIONS TO SET ALL OF THE PARAMETERS FOR THE MESS FILE
def mass_params(well_info, bath_info, etrans_dct):
    """ Determine the mass parameters used to
        define the energy transfer model for master equation simulations.

        Function first assesses if a user has supplied mass parameters
        by way of ___. If masses have not been provided, then the masses
        will be simply calculated using the geometries of the well and
        bath species.

        :param well_info: spc_info object for well species
        :type well_info: mechanalyzer.inf.spc object
        :param bath_info: spc_info object for bath species
        :type bath_info: mechanalyzer.inf.spc object
        :param etrans_dct:
    """

    mass = etrans_dct.get('mass', None)
    if mass is not None:
        ioprinter.info_message('  - Using the user input values...')
        [mass1, mass2] = mass
    else:
        ioprinter.info_message('  - Obtaining masses from geometries...')
        geo = automol.inchi.geometry(well_info[0])
        mass1 = sum(automol.geom.masses(geo))

        geo = automol.inchi.geometry(bath_info[0])
        mass2 = sum(automol.geom.masses(geo))

    return mass1, mass2


def lj_params(well_info, bath_info, etrans_dct):
    """ Determine the Lennard-Jones (LJ) epsilon and sigma parameters used to
        define the energy transfer model for master equation simulations.

        Function first assesses if a user has supplied mass parameters
        by way of ___. If masses have not been provided, then the masses
        will be simply calculated using the geometries of the well and
    """

    sig1, eps1, sig2, eps2 = None, None, None, None

    ljpar = etrans_dct.get('lj', None)
    if ljpar is not None:

        if isinstance(ljpar, list):

            ioprinter.info_message('  - Using the user input values...')
            [sig1, eps1, sig2, eps2] = ljpar

        elif ljpar == 'estimate':

            ioprinter.info_message('- Estimating the parameters...')
            well_ich = well_info[0]
            well_geo = automol.inchi.geometry(well_ich)
            params = automol.etrans.effective_model(
                well_ich, bath_info[0])
            if params is not None:
                bath_model, tgt_model = params
                ioprinter.info_message(
                    '    - Series to use for estimation for estimation...')
                ioprinter.info_message(
                    f'      Bath: {bath_model}, Target: {tgt_model} ')

                ioprinter.info_message(
                    '    - Effective atom numbers for estimation...')
                n_heavy = automol.geom.atom_count(well_geo, 'H', match=False)
                ioprinter.info_message(
                    '      N_heavy: ', n_heavy)
                sig, eps = automol.etrans.eff.lennard_jones_params(
                    n_heavy, bath_model, tgt_model)
                sig1, eps1, sig2, eps2 = sig, eps, sig, eps

        # elif ljpar == 'read':
        #     ioprinter.info_message('- Reading the filesystem...')
        #     ljs_lvl = etrans_dct.get('ljlvl', None)
        #     if ljs_lvl is not None:
        #         # Get the levels into theory objects
        #         pf_filesystems = 0
        #         sig1, eps1, sig2, eps2 = _read_lj(pf_filesystems)

    else:
        sig1, eps1, sig2, eps2 = None, None, None, None

    return sig1, eps1, sig2, eps2


def edown_params(well_info, bath_info, etrans_dct, ljpar=None):
    """ Energy down model parameters
    """

    efactor, epower, ecutoff = None, None, None

    edown = etrans_dct.get('edown', None)

    if edown is not None:

        if isinstance(edown, list):

            ioprinter.info_message('  - Using the user input values...')
            [efactor, epower, ecutoff] = edown

        elif edown == 'estimate':

            assert ljpar is not None

            ioprinter.info_message('  - Estimating the parameters...')
            well_ich = well_info[0]
            well_geo = automol.inchi.geometry(well_ich)
            params = automol.etrans.effective_model(
                well_ich, bath_info[0])
            if params is not None:
                bath_model, tgt_model = params
                ioprinter.info_message(
                    '    - Series to use for estimation for estimation...')
                ioprinter.info_message(
                    f'      Bath: {bath_model}, Target: {tgt_model} ')

                ioprinter.info_message(
                    '    - Calculating the LJ collisional frequencies...')
                ioprinter.info_message(
                    '    - Effective atom numbers for estimation...')
                sig, eps, mass1, mass2 = ljpar
                n_eff = automol.etrans.eff.effective_rotor_count(well_geo)
                ioprinter.info_message(
                    '      N_eff: ', n_eff)
                efactor, epower = automol.etrans.eff.alpha(
                    n_eff, eps, sig, mass1, mass2, bath_model, tgt_model)
                ecutoff = 15.0

        # elif edown == 'read':
        #     ioprinter.info_message('  - Reading the filesystem...')
        #     edownlvl = etrans_dct.get('edownlvl', None)
        #     if edownlvl is not None:
        #         # NEED: Get the levels into theory objects
        #         pf_filesystems = 0
        #         efactor = _read_alpha(pf_filesystems)

    return efactor, epower, ecutoff


# FUNCTION TO HANDLE BUILDING ETRANS OBJECTS
def build_etrans_dct(spc_dct_i):
    """  Build an energy transfer dict from a spc dct
    """

    etrans_dct = {}

    mass = spc_dct_i.get('mass', None)
    if mass is not None:
        etrans_dct['mass'] = mass

    ljpar = spc_dct_i.get('lj', None)
    if ljpar is not None:
        etrans_dct['lj'] = ljpar

    edown = spc_dct_i.get('edown', None)
    if edown is not None:
        etrans_dct['edown'] = edown

    return etrans_dct


def set_etrans_well(rxn_lst, spc_dct):
    """ Build info object for reference well on PES
    """

    well_dct = None

    _, (reacs, prods) = rxn_lst[0]

    if len(reacs) == 1:
        well_dct = spc_dct[reacs[0]]
    elif len(prods) == 1:
        well_dct = spc_dct[prods[0]]
    else:
        rct1_dct = spc_dct[reacs[0]]
        rct2_dct = spc_dct[reacs[1]]
        rct1_count = automol.geom.count(
            automol.inchi.geometry(rct1_dct['inchi']))
        rct2_count = automol.geom.count(
            automol.inchi.geometry(rct2_dct['inchi']))
        if rct1_count > rct2_count:
            well_dct = rct1_dct
        else:
            well_dct = rct2_dct

    well_info = sinfo.from_dct(well_dct)

    return well_info


def set_bath(spc_dct, etrans_dct):
    """ Build nfo object for the bath
    """

    # Try to obtain bath set by the user, otherwise use N2
    bath_name = etrans_dct.get('bath', None)
    bath_dct = spc_dct.get(bath_name, None)
    if bath_dct is not None:
        bath_info = sinfo.from_dct(bath_dct)
        ioprinter.info_message(f'  - Using bath {bath_name} input by user')
    else:
        bath_info = ['InChI=1S/Ar', 0, 1]
        ioprinter.info_message(
            '  - No bath provided, using Argon as bath')

    return bath_info
