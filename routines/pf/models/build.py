"""
  Read the save filesystem for all of the required information specified by
    (1) the models specified for partition function and
    (2) the electronic structure levels
  in order to write portions of MESS strings for species and reaction paths
  and calculate electronic and zero-point vibrational energies.
"""

import autofile
from routines.pf.models import ene
from routines.pf.models import typ
from routines.pf.models import _rot as rot
from routines.pf.models import _tors as tors
from routines.pf.models import _sym as sym
from routines.pf.models import _vib as vib
from routines.pf.models import _flux as flux
from routines.pf.models import _fs as fs
from routines.pf.models import _util as util
from lib.structure import tors as torsprep
from lib.phydat import phycon
from lib import filesys


# General readers
def read_spc_data(spc_dct_i, spc_name,
                  chn_pf_models, chn_pf_levels,
                  run_prefix, save_prefix,
                  ref_pf_models=(), ref_pf_levels=()):
    """ Determines which block writer to use tau
    """
    print(('\n++++++++++++++++++++++++++++++++++++++++++++++++' +
           '++++++++++++++++++++++++++++++++++++++'))
    print('\nReading filesystem info for {}'.format(spc_name))

    vib_model, tors_model = chn_pf_models['vib'], chn_pf_models['tors']
    if typ.is_atom(spc_dct_i):
        inf_dct = atm_data(
            spc_dct_i,
            chn_pf_models, chn_pf_levels,
            ref_pf_models, ref_pf_levels,
            run_prefix, save_prefix)
        writer = 'atom_block'
    else:
        if vib_model == 'tau' or tors_model == 'tau':
            inf_dct = tau_data(
                spc_dct_i,
                chn_pf_models, chn_pf_levels,
                run_prefix, save_prefix, saddle=False)
            writer = 'tau_block'
        else:
            inf_dct = mol_data(
                spc_dct_i,
                chn_pf_models, chn_pf_levels,
                ref_pf_models, ref_pf_levels,
                run_prefix, save_prefix, saddle=False)
            writer = 'species_block'

    # Add writer to inf dct
    inf_dct['writer'] = writer

    return inf_dct


def read_ts_data(ts_dct, tsname, reac_dcts, 
                 chn_pf_models, chn_pf_levels,
                 run_prefix, save_prefix,
                 ts_class, ts_sadpt, ts_nobarrier,
                 ref_pf_models=(), ref_pf_levels=()):
    """ Determine which block function to useset block functions
    """

    print(('\n++++++++++++++++++++++++++++++++++++++++++++++++' +
           '++++++++++++++++++++++++++++++++++++++'))
    print('\nReading filesystem info for {}'.format(tsname))

    # Get all of the information for the filesystem
    if not typ.var_radrad(ts_class):

        # Set up the saddle point keyword
        sadpt = True
        search = ts_dct.get('ts_search')
        if search is not None:
            if 'vtst' in search:
                sadpt = False

        # Build MESS string for TS at a saddle point
        if ts_sadpt == 'pst':
            inf_dct = {}
            writer = 'pst_block'
        elif ts_sadpt == 'rpvtst':
            inf_dct = rpvtst_data(
                ts_dct, reac_dcts,
                chn_pf_models, chn_pf_levels,
                ref_pf_models, ref_pf_levels,
                run_prefix, save_prefix, sadpt=sadpt)
            writer = 'rpvtst_block'
        else:
            inf_dct = mol_data(
                ts_dct,
                chn_pf_models, chn_pf_levels,
                ref_pf_models, ref_pf_levels,
                run_prefix, save_prefix, saddle=True)
            writer = 'species_block'
    else:

        # Build MESS string for TS with no saddle point
        if ts_nobarrier == 'pst':
            inf_dct = {}
            writer = 'pst_block'
        elif ts_nobarrier == 'rpvtst':
            inf_dct = rpvtst_data(
                ts_dct, reac_dcts,
                chn_pf_models, chn_pf_levels,
                ref_pf_models, ref_pf_levels,
                run_prefix, save_prefix, sadpt=False)
            writer = 'rpvtst_block'
        elif ts_nobarrier == 'vrctst':
            inf_dct = flux_data(
                ts_dct,
                chn_pf_models, chn_pf_levels,
                ref_pf_models, ref_pf_levels)
            writer = 'vrctst_block'

    # Add writer to inf dct
    # print(inf_dct)
    inf_dct['writer'] = writer

    return inf_dct


# Data Readers
def atm_data(spc_dct_i,
             chn_pf_models, chn_pf_levels, ref_pf_models, ref_pf_levels,
             run_prefix, save_prefix):
    """ Pull all neccessary info for the atom
    """

    # Set up all the filesystem objects using models and levels
    pf_filesystems = fs.pf_filesys(
        spc_dct_i, chn_pf_levels, run_prefix, save_prefix, False)

    print('\nObtaining the geometry...')
    geom = rot.read_geom(pf_filesystems)

    print('\nObtaining the electronic energy...')
    ene_chnlvl = ene.read_energy(
        spc_dct_i, pf_filesystems, chn_pf_models, chn_pf_levels,
        read_ene=True, read_zpe=False)

    ene_reflvl = None
    _, _ = ref_pf_models, ref_pf_levels
    zpe_chnlvl = None

    # Create info dictionary
    inf_dct = {
        'geom': geom,
        'sym_factor': 1.0,
        'freqs': [],
        'mess_hr_str': '',
        'mass': util.atom_mass(spc_dct_i),
        'elec_levels': spc_dct_i['elec_levels'],
        'ene_chnlvl': ene_chnlvl,
        'ene_reflvl': ene_reflvl,
        'zpe_chnlvl': zpe_chnlvl
    }

    return inf_dct


def mol_data(spc_dct_i,
             chn_pf_models, chn_pf_levels, ref_pf_models, ref_pf_levels,
             run_prefix, save_prefix, saddle=False):
    """ Pull all of the neccessary information from the filesystem for a species
    """

    # Initialize all of the elements of the inf dct
    geom, sym_factor, freqs, imag, elec_levels = None, None, None, None, None
    allr_str, mdhr_dat = '', ''
    xmat, rovib_coups, rot_dists = None, None, None

    # Set up all the filesystem objects using models and levels
    pf_filesystems = fs.pf_filesys(
        spc_dct_i, chn_pf_levels, run_prefix, save_prefix, saddle)

    # Set information for transition states
    [cnf_fs, _, min_cnf_locs, _, _] = pf_filesystems['harm']
    # cnf_path = cnf_fs[-1].path(min_cnf_locs)
    frm_bnd_keys, brk_bnd_keys = util.get_bnd_keys(
        cnf_fs, min_cnf_locs, saddle)
    rxn_class = util.set_rxn_class(spc_dct_i, saddle)

    # Obtain rotor information used to determine new information
    print('\nPreparing internal rotor info building partition functions...')
    rotors = tors.build_rotors(
        spc_dct_i, pf_filesystems, chn_pf_models, chn_pf_levels,
        rxn_class=rxn_class,
        frm_bnd_keys=frm_bnd_keys, brk_bnd_keys=brk_bnd_keys)

    if typ.nonrigid_tors(chn_pf_models, rotors):
        run_path = fs.make_run_path(pf_filesystems, 'tors')
        tors_strs = tors.make_hr_strings(
            rotors, run_path, chn_pf_models['tors'])
        [allr_str, hr_str, _, prot_str, mdhr_dat] = tors_strs

    # Obtain rotation partition function information
    print('\nObtaining info for rotation partition function...')
    geom = rot.read_geom(pf_filesystems)

    if typ.nonrigid_rotations(chn_pf_models):
        rovib_coups, rot_dists = rot.read_rotational_values(pf_filesystems)

    # Obtain vibration partition function information
    print('\nObtaining the vibrational frequencies and zpves...')
    if typ.nonrigid_tors(chn_pf_models, rotors):
        freqs, imag, zpe, _ = vib.tors_projected_freqs_zpe(
            pf_filesystems, hr_str, prot_str, saddle=saddle)
        if 'mdhrv' in chn_pf_models['tors']:
            freqs = ()
    else:
        freqs, imag, zpe = vib.read_harmonic_freqs(
            pf_filesystems, saddle=saddle)

    if typ.anharm_vib(chn_pf_models):
        xmat = vib.read_anharmon_matrix(pf_filesystems)

    # Obtain symmetry factor
    print('\nDetermining the symmetry factor...')
    sym_factor = sym.symmetry_factor(
        pf_filesystems, chn_pf_models, spc_dct_i, rotors,
        frm_bnd_keys=frm_bnd_keys, brk_bnd_keys=brk_bnd_keys)

    # Obtain electronic energy levels
    elec_levels = spc_dct_i['elec_levels']

    # Obtain energy levels
    print('\nObtaining the electronic energy...')
    chn_ene = ene.read_energy(
        spc_dct_i, pf_filesystems, chn_pf_models, chn_pf_levels,
        read_ene=True, read_zpe=False)
    print('chn_ene', chn_ene)
    ene_chnlvl = chn_ene + zpe

    ene_reflvl = None
    _, _ = ref_pf_models, ref_pf_levels
    # if chn_model == ref_model:
    #     ene_reflvl = ene_chnlvl
    # else:
    #     ene_reflvl = get_fs_ene_zpe(spc_dct, prod,
    #                                 thy_dct, model_dct, model,
    #                                 save_prefix, saddle=False,
    #                                 read_ene=True, read_zpe=True)

    # Create info dictionary
    keys = ['geom', 'sym_factor', 'freqs', 'imag', 'elec_levels',
            'mess_hr_str', 'mdhr_dat',
            'xmat', 'rovib_coups', 'rot_dists',
            'ene_chnlvl', 'ene_reflvl', 'zpe_chnlvl']
    vals = [geom, sym_factor, freqs, imag, elec_levels,
            allr_str, mdhr_dat,
            xmat, rovib_coups, rot_dists,
            ene_chnlvl, ene_reflvl, zpe]
    inf_dct = dict(zip(keys, vals))

    return inf_dct


# VRCTST
def flux_data(ts_dct,
              chn_pf_models, chn_pf_levels,
              ref_pf_models, ref_pf_levels):
    """ Grab the flux file from the filesystem
    """

    # Fake setting for plugin
    _, _, _ = chn_pf_models, ref_pf_models, ref_pf_levels

    # Read the flux file from the filesystem
    _, ts_save_path, _, _ = fs.set_rpath_filesys(
        ts_dct, chn_pf_levels['rpath'][1])

    flux_str = flux.read_flux(ts_save_path)

    # Create info dictionary
    inf_dct = {'flux_str': flux_str}

    return inf_dct


# VTST
def rpvtst_data(ts_dct, reac_dcts,
                chn_pf_models, chn_pf_levels, ref_pf_models, ref_pf_levels,
                run_prefix, save_prefix, sadpt=False):
    """ Pull all of the neccessary information from the
        filesystem for a species
    """

    # Fake setting for plugin
    _, _, _ = chn_pf_models, ref_pf_models, ref_pf_levels

    # Set up all the filesystem objects using models and levels
    if sadpt:
        # Set up filesystems and coordinates for saddle point
        # Scan along RxnCoord is under THY/TS/CONFS/cid/Z
        pf_filesystems = fs.pf_filesys(
            ts_dct, chn_pf_levels, run_prefix, save_prefix, True)
        tspaths = pf_filesystems['harm']
        [_, cnf_save_path, min_locs, _, cnf_run_fs] = tspaths
        ts_run_path = cnf_run_fs[-1].path(min_locs)

        # Set TS reaction coordinate
        frm_name = 'IRC'
        scn_vals = fs.get_rxn_scn_coords(cnf_save_path, frm_name)
        scn_vals.sort()
        scn_ene_info = chn_pf_levels['ene'][1][0][1]  # fix to be ene lvl
        scn_prefix = cnf_save_path
    else:
        # Set up filesystems and coordinates for reaction path
        # Scan along RxnCoord is under THY/TS/Z
        tspaths = fs.set_rpath_filesys(
            ts_dct, chn_pf_levels['rpath'][1])
        ts_run_path, ts_save_path, _, thy_save_path = tspaths

        # Set TS reaction coordinate
        frm_bnd_keys, _ = util.get_bnd_keys2(ts_save_path, True)
        frm_name = util.get_rxn_coord_name(
            ts_save_path, frm_bnd_keys, sadpt=sadpt, zma_locs=(0,))
        scn_vals = fs.get_rxn_scn_coords(thy_save_path, frm_name)
        scn_vals.sort()
        scn_ene_info = chn_pf_levels['rpath'][1][0]
        scn_prefix = thy_save_path

    # Modify the scn thy info
    print('scn thy info', scn_ene_info)
    print('scn vals', scn_vals)
    mod_scn_ene_info = filesys.inf.modify_orb_restrict(
        filesys.inf.get_spc_info(ts_dct), scn_ene_info)
    # scn thy info [[1.0, ['molpro2015', 'ccsd(t)', 'cc-pvdz', 'RR']]]

    # Need to read the sp vals along the scan. add to read
    ref_ene = 0.0
    enes, geoms, grads, hessians, _ = torsprep.read_hr_pot(
        [frm_name], [scn_vals],
        scn_prefix,
        mod_scn_ene_info, ref_ene,
        constraint_dct=None,   # No extra frozen treatments
        read_geom=True,
        read_grad=True,
        read_hess=True)
    freqs = torsprep.calc_hr_frequencies(
        geoms, grads, hessians, ts_run_path)

    # Get the energies and zpes at R_ref
    if not sadpt:
        idx, ene_hs_sr_ref, ene_hs_mr_ref = ene.rpath_ref_idx(
            ts_dct, scn_vals, frm_name, scn_prefix,
            chn_pf_levels['ene'],
            chn_pf_levels['rpath'][1])
    zpe_ref = (sum(freqs[(idx,)]) / 2.0) * phycon.WAVEN2KCAL

    # Get the reactants and infinite seperation energy
    reac_ene = 0.0
    inf_ene = 0.0
    for dct in reac_dcts:
        pf_filesystems = fs.pf_filesys(
            dct, chn_pf_levels, run_prefix, save_prefix, False)
        pf_levels = {
            'ene': chn_pf_levels['ene'],
            'harm': chn_pf_levels['harm']
        }
        reac_ene += ene.read_energy(
            dct, pf_filesystems, chn_pf_models, pf_levels,
            read_ene=True, read_zpe=False)

        print('rpath', chn_pf_levels['rpath'][1])
        pf_levels = {
            'ene': ['mlvl', [[1.0, chn_pf_levels['rpath'][1][2]]]],
            'harm': chn_pf_levels['harm']
        }
        inf_ene += ene.read_energy(
            dct, pf_filesystems, chn_pf_models, pf_levels,
            read_ene=True, read_zpe=False)

    # Scale the scn values
    if sadpt:
        scn_vals = [val / 100.0 for val in scn_vals]
    # scn_vals = [val * phycon.BOHR2ANG for val in scn_vals]

    # Grab the values from the read
    inf_dct = {}
    inf_dct['rpath'] = []
    pot_info = zip(scn_vals, enes.values(), geoms.values(), freqs.values())
    for rval, pot, geo, frq in pot_info:

        # Scale the r-values

        # Get the relative energy (edit for radrad scans)
        zpe = (sum(frq) / 2.0) * phycon.WAVEN2KCAL
        if sadpt:
            zero_ene = (pot + zpe) * phycon.KCAL2EH
        else:
            print('enes')
            print(reac_ene)
            print(ene_hs_sr_ref)
            print(inf_ene)
            print(ene_hs_mr_ref)
            print(pot * phycon.KCAL2EH)

            elec_ene = (
                reac_ene + 
                ene_hs_sr_ref - inf_ene -
                ene_hs_mr_ref + pot * phycon.KCAL2EH
            )
            zpe_pt = zpe - zpe_ref
            zero_ene = elec_ene + zpe_pt

        # ENE
        # ene = (reac_ene +
        #        ene_hs_sr(R_ref) - ene_hs_sr(inf) +
        #        ene_ls_mr(R_ref) - ene_hs_mr(R_ref) +
        #        ene_ls_mr(R) - ene_ls_mr(R_ref))
        # ene = (reac_ene +
        #        ene_hs_sr(R_ref) - ene_hs_sr(inf) -
        #        ene_hs_mr(R_ref) + ene_ls_mr(R))
        # inf_sep_ene = reac_ene + hs_sr_ene - hs_mr_ene
        # inf_sep_ene_p = (reac_ene +
        #                  hs_sr_ene(R_ref) - ene_hs_sr(inf) +
        #                  ls_mr_ene(R_ref) - hs_mr_ene(R_ref))
        # ene = inf_sep_ene_p + ene_ls_mr(R) - ene_ls_mr(R_ref)
        # ZPE
        # zpe = zpe(R) - zpe(inf)
        # or
        # zpe = zpe_ls_mr(R) - zpe_ls_mr(R_ref)

        # Set values constant across the scan
        elec_levels = ts_dct['elec_levels']

        # Create info dictionary and append to lst
        keys = ['rval', 'geom', 'freqs', 'elec_levels', 'ene_chnlvl']
        vals = [rval, geo, frq, elec_levels, zero_ene]
        inf_dct['rpath'].append(dict(zip(keys, vals)))

    # Calculate and store the imaginary mode
    if sadpt:
        _, imag, _ = vib.read_harmonic_freqs(
            pf_filesystems, saddle=True)
        ts_idx = scn_vals.index(0.00)
    else:
        imag = None
        ts_idx = 0
    inf_dct.update({'imag': imag})
    inf_dct.update({'ts_idx': ts_idx})

    return inf_dct


# TAU
def tau_data(spc_dct_i,
             chn_pf_models, chn_pf_levels,
             run_prefix, save_prefix, saddle=False):
    """ Read the filesystem to get information for TAU
    """

    frm_bnd_keys = ()
    brk_bnd_keys = ()

    # Set up all the filesystem objects using models and levels
    pf_filesystems = fs.pf_filesys(
        spc_dct_i, chn_pf_levels, run_prefix, save_prefix, saddle)
    [harm_cnf_fs, _,
     harm_min_locs, harm_save, _] = pf_filesystems['harm']
    # [tors_cnf_fs, _, tors_min_locs, _, _] = pf_filesystems['tors']

    # Get the conformer filesys for the reference geom and energy
    if harm_min_locs:
        geom = harm_cnf_fs[-1].file.geometry.read(harm_min_locs)
        min_ene = harm_cnf_fs[-1].file.energy.read(harm_min_locs)

    # Set the filesystem
    tau_save_fs = autofile.fs.tau(harm_save)

    # Set the ground and reference energy to set values for now
    rxn_class = None

    # Get the rotor info
    rotors = tors.build_rotors(
        spc_dct_i, pf_filesystems, chn_pf_models,
        chn_pf_levels,
        rxn_class=rxn_class,
        frm_bnd_keys=frm_bnd_keys, brk_bnd_keys=brk_bnd_keys)

    run_path = fs.make_run_path(pf_filesystems, 'tors')
    tors_strs = tors.make_hr_strings(
        rotors, run_path, chn_pf_models['tors'])
    [_, hr_str, flux_str, prot_str, _] = tors_strs

    # Use model to determine whether to read grads and hessians
    vib_model = chn_pf_models['vib']
    freqs = ()
    _, _, proj_zpve, harm_zpve = vib.tors_projected_freqs_zpe(
        pf_filesystems, hr_str, prot_str, saddle=False)
    zpe_chnlvl = proj_zpve * phycon.EH2KCAL

    # Set reference energy to harmonic zpve
    db_style = 'directory'
    reference_energy = harm_zpve * phycon.EH2KCAL
    if vib_model == 'tau':
        if db_style == 'directory':
            tau_locs = [locs for locs in tau_save_fs[-1].existing()
                        if tau_save_fs[-1].file.hessian.exists(locs)]
        elif db_style == 'jsondb':
            tau_locs = [locs for locs in tau_save_fs[-1].json_existing()
                        if tau_save_fs[-1].json.hessian.exists(locs)]
    else:
        if db_style == 'directory':
            tau_locs = tau_save_fs[-1].existing()
        elif db_style == 'jsondb':
            tau_locs = tau_save_fs[-1].json_existing()

    # Read the geom, ene, grad, and hessian for each sample
    samp_geoms, samp_enes, samp_grads, samp_hessians = [], [], [], []
    for locs in tau_locs:

        # print('Reading tau info at path {}'.format(
        #     tau_save_fs[-1].path(locs)))

        if db_style == 'directory':
            geo = tau_save_fs[-1].file.geometry.read(locs)
        elif db_style == 'jsondb':
            geo = tau_save_fs[-1].json.geometry.read(locs)

        geo_str = autofile.data_types.swrite.geometry(geo)
        samp_geoms.append(geo_str)

        if db_style == 'directory':
            tau_ene = tau_save_fs[-1].file.energy.read(locs)
        elif db_style == 'jsondb':
            tau_ene = tau_save_fs[-1].json.energy.read(locs)
        rel_ene = (tau_ene - min_ene) * phycon.EH2KCAL
        ene_str = autofile.data_types.swrite.energy(rel_ene)
        samp_enes.append(ene_str)

        if vib_model == 'tau':
            if db_style == 'directory':
                grad = tau_save_fs[-1].file.gradient.read(locs)
            elif db_style == 'jsondb':
                grad = tau_save_fs[-1].json.gradient.read(locs)
            grad_str = autofile.data_types.swrite.gradient(grad)
            samp_grads.append(grad_str)

            if db_style == 'directory':
                hess = tau_save_fs[-1].file.hessian.read(locs)
            elif db_style == 'jsondb':
                hess = tau_save_fs[-1].json.hessian.read(locs)
            hess_str = autofile.data_types.swrite.hessian(hess)
            samp_hessians.append(hess_str)

    # Read a geometry, grad, and hessian for a reference geom if needed
    ref_geom, ref_grad, ref_hessian = [], [], []
    if vib_model != 'tau':

        # Get harmonic filesystem information
        [harm_save_fs, _, harm_min_locs, _, _] = pf_filesystems['harm']

        # Read the geometr, gradient, and Hessian
        geo = harm_save_fs[-1].file.geometry.read(harm_min_locs)
        geo_str = autofile.data_types.swrite.geometry(geo)
        ref_geom.append(geo_str)

        grad = harm_save_fs[-1].file.gradient.read(harm_min_locs)
        grad_str = autofile.data_types.swrite.gradient(grad)
        ref_grad.append(grad_str)

        hess = harm_save_fs[-1].file.hessian.read(harm_min_locs)
        hess_str = autofile.data_types.swrite.hessian(hess)
        ref_hessian.append(hess_str)

    # Obtain symmetry factor
    print('\nDetermining the symmetry factor...')
    sym_factor = sym.symmetry_factor(
        pf_filesystems, chn_pf_models, spc_dct_i, rotors,
        frm_bnd_keys=(), brk_bnd_keys=())

    # Create info dictionary
    keys = ['geom', 'sym_factor', 'elec_levels', 'freqs', 'flux_mode_str',
            'samp_geoms', 'samp_enes', 'samp_grads', 'samp_hessians',
            'ref_geom', 'ref_grad', 'ref_hessian',
            'zpe_chnlvl', 'reference_energy']
    vals = [geom, sym_factor, spc_dct_i['elec_levels'], freqs, flux_str,
            samp_geoms, samp_enes, samp_grads, samp_hessians,
            ref_geom, ref_grad, ref_hessian,
            zpe_chnlvl, reference_energy]
    inf_dct = dict(zip(keys, vals))

    return inf_dct
