""" es_runners for coordinate scans
"""

from mechroutines.es.runner import scan
from mechlib import filesys
from mechlib.structure import tors as torsprep
from mechlib.amech_io import printer as ioprinter


def hindered_rotor_scans(
        zma, spc_info, mod_thy_info, thy_save_fs,
        zma_run_path, zma_save_path,
        run_tors_names, run_tors_grids,
        script_str, overwrite,
        scn_typ='relaxed',
        saddle=False, const_names=None,
        retryfail=True, chkstab=None, **opt_kwargs):
    """ Perform scans over each of the torsional coordinates
    """

    # Set appropriate value for check stability
    # If not set, don't check if saddle=True
    if chkstab is None:
        chkstab = bool(not saddle)

    ioprinter.run_rotors(run_tors_names, const_names)

    # for tors_name, tors_grid in zip(tors_names, tors_grids):
    for tors_names, tors_grids in zip(run_tors_names, run_tors_grids):

        ioprinter.info_message(
            'Running Rotor: {}...'.format(tors_names),
            newline=1)

        # Setting the constraints
        constraint_dct = torsprep.build_constraint_dct(
            zma, const_names, tors_names)

        # Setting the filesystem
        # print('hr constraint dct', constraint_dct)
        scn_run_fs = filesys.build.scn_fs_from_cnf(
            zma_run_path, constraint_dct=constraint_dct)
        scn_save_fs = filesys.build.scn_fs_from_cnf(
            zma_save_path, constraint_dct=constraint_dct)

        ioprinter.info_message('Saving any HR in run filesys...', newline=1)
        if constraint_dct is None:
            scan.save_scan(
                scn_run_fs=scn_run_fs,
                scn_save_fs=scn_save_fs,
                scn_typ=scn_typ,
                coo_names=tors_names,
                mod_thy_info=mod_thy_info,
                in_zma_fs=True)
        else:
            scan.save_cscan(
                cscn_run_fs=scn_run_fs,
                cscn_save_fs=scn_save_fs,
                scn_typ=scn_typ,
                constraint_dct=constraint_dct,
                mod_thy_info=mod_thy_info,
                in_zma_fs=True)

        ioprinter.info_message('Running any HR Scans if needed...', newline=1)
        scan.run_scan(
            zma=zma,
            spc_info=spc_info,
            mod_thy_info=mod_thy_info,
            thy_save_fs=thy_save_fs,
            coord_names=tors_names,
            coord_grids=tors_grids,
            scn_run_fs=scn_run_fs,
            scn_save_fs=scn_save_fs,
            scn_typ=scn_typ,
            script_str=script_str,
            overwrite=overwrite,
            update_guess=True,
            reverse_sweep=True,
            saddle=saddle,
            constraint_dct=constraint_dct,
            retryfail=retryfail,
            chkstab=chkstab,
            **opt_kwargs
        )

        ioprinter.info_message(
            'Saving any newly run HR scans in run filesys...',
            newline=1)
        if constraint_dct is None:
            scan.save_scan(
                scn_run_fs=scn_run_fs,
                scn_save_fs=scn_save_fs,
                scn_typ=scn_typ,
                coo_names=tors_names,
                mod_thy_info=mod_thy_info,
                in_zma_fs=True)
        else:
            scan.save_cscan(
                cscn_run_fs=scn_run_fs,
                cscn_save_fs=scn_save_fs,
                scn_typ=scn_typ,
                constraint_dct=constraint_dct,
                mod_thy_info=mod_thy_info,
                in_zma_fs=True)
