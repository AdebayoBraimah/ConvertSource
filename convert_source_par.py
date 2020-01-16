# -*- coding: utf-8 -*-
'''
PAR REC specific functions for convert_source. Primarily intended for converting and renaming PAR REC files to BIDS NifTi.
'''

# Import packages and modules
import json
import re
import os
import sys
import subprocess
import nibabel as nib
import gzip
import numpy as np
import platform

# Import third party packages and modules
# import ...

# Define functions

def get_etl(par_file):
    '''
    Gets EPI factor (Echo Train Length) from Philips' PAR Header.
    
    N.B.: This is done via a regEx search as the PAR header is not assumed to change significantly between scanners.
    
    Arguments:
        par_file (string): Absolute filepath to PAR header file
        
    Returns:
        etl (float): Echo Train Length
    '''
    regexp = re.compile(r'.    EPI factor        <0,1=no EPI>     :   .*?([0-9.-]+)')  # Search string for RegEx
    with open(par_file) as f:
        for line in f:
            match = regexp.match(line)
            if match:
                etl = match.group(1)
                etl = int(etl)
    return etl

def get_wfs(par_file):
    '''
    Gets Water Fat Shift from Philips' PAR Header.
    
    N.B.: This is done via a regEx search as the PAR header is not assumed to change significantly between scanners.
    
    Arguments:
        par_file (string): Absolute filepath to PAR header file
        
    Returns:
        wfs (float): Water Fat Shift
    '''
    regexp = re.compile(
        r'.    Water Fat shift \[pixels\]           :   .*?([0-9.-]+)')  # Search string for RegEx, escape the []
    with open(par_file) as f:
        for line in f:
            match = regexp.match(line)
            if match:
                wfs = match.group(1)
                wfs = float(wfs)
    return wfs

def get_red_fact(par_file):
    '''
    Extracts parallel reduction factor in-plane value (SENSE) from the file description in the PAR REC header 
    for Philips MR scanners. This reduction factor is assumed to be 1 if a value cannot be found from witin
    the PAR REC header.
    
    N.B.: This is done via a regEx search as the PAR header is not assumed to change significantly between scanners.
    
    Arguments:
        par_file (string): Absolute filepath to PAR header file
        
    Returns:
        red_fact (float): parallel reduction factor in-plane value (e.g. SENSE factor)
    '''
    
    # Read file
    red_fact = ""
    regexp = re.compile(r' SENSE *?([0-9.-]+)')
    with open(par_file) as f:
        for line in f:
            match = regexp.search(line)
            if match:
                red_fact = match.group(1)
                red_fact = float(red_fact)
            else:
                red_fact = float(1)

    return red_fact

def get_mb(par_file):
    '''
    Extracts multi-band acceleration factor from from Philips' PAR Header.
    
    N.B.: This is done via a regEx search as the PAR header does not normally store this value.
    
    Arguments:
        par_file (string): Absolute filepath to PAR header file
        
    Returns:
        mb (int): multi-band acceleration factor
    '''

    # Initialize mb to 1
    mb = 1
    
    regexp = re.compile(r' MB *?([0-9.-]+)')
    with open(par_file) as f:
        for line in f:
            match = regexp.search(line)
            if match:
                mb = match.group(1)
                mb = int(mb)

    return mb

def get_scan_time(par_file):
    '''
    Gets the acquisition duration (scan time, in s) from the PAR header.
    
    N.B.: This is done via a regEx search as the PAR header is not assumed to change significantly between scanners.
    
    Arguments:
        par_file (string): Absolute filepath to PAR header file
        
    Returns:
        scan_time (float or string): Acquisition duration (scan time, in s). If not in header, return is a string 'unknown'
    '''
    
    scan_time = 'unknown'
    
    regexp = re.compile(
        r'.    Scan Duration \[sec\]                :   .*?([0-9.-]+)')  # Search string for RegEx, escape the []
    with open(par_file) as f:
        for line in f:
            match = regexp.match(line)
            if match:
                scan_time = match.group(1)
                scan_time = float(scan_time)
    return scan_time

    return scan_time

def get_par_scan_tech(par_file, search_dict, keep_unknown=True, verbose=False):
    '''
    Searches PAR file header for scan technique/MR modality used in accordance with the search terms provided by the
    nested dictionary. A regular expression (regEx) search string is defined and searched for conventional PAR headers.
    
    Note: This function is still undergoing active development.
    
    Arguments:
        search_dict (dict): Nested dictionary from the 'read_config' function
        par_file (string): PAR filename with absolute filepath
    
    Returns: 
        None
    '''
    
    mod_found = False
    
    # Define regEx search string
    regexp = re.compile(r'.    Technique                          :  .*', re.M | re.I)
    
    # Open and search PAR header file
    with open(par_file) as f:
        for line in f:
            match_ = regexp.match(line)
            if match_:
                par_scan_tech_str = match_.group()
    
    # Search Scan Technique with search terms
    for key,item in search_dict.items():
        for dict_key,dict_item in search_dict[key].items():
            if isinstance(dict_item,list):
                if list_in_substr(dict_item,par_scan_tech_str):
                    mod_found = True
                    if verbose:
                        print(f"{key} - {dict_key}: {dict_item}")
                    scan_type = key
                    scan = dict_key
                    if scan_type.lower() == 'dwi':
                        data_to_bids_dwi(bids_out_dir,file,sub,scan,meta_dict_com,meta_dict_dwi="",ses="",scan_type=scan_type)
                    elif scan_type.lower() == 'fmap':
                        data_to_bids_fmap(bids_out_dir,file,sub,scan,meta_dict_com,meta_dict_fmap="",ses="",scan_type=scan_type)
                    else:
                        data_to_bids_anat(bids_out_dir,file,sub,scan,meta_dict_com,meta_dict_anat="",ses="",scan_type=scan_type)
                    if mod_found:
                        break
            elif isinstance(dict_item,dict):
                tmp_dict = search_dict[key]
                for d_key,d_item in tmp_dict[dict_key].items():
                    if list_in_substr(d_item,par_scan_tech_str):
                        mod_found = True
                        if verbose:
                            print(f"{key} - {dict_key} - {d_key}: {d_item}")
                        scan_type = key
                        scan = dict_key
                        task = d_key
                        if scan_type.lower() == 'func':
                            data_to_bids_func(bids_out_dir,file,sub,scan,task="",meta_dict_com,meta_dict_func="",ses="",scan_type=scan_type)
                        elif scan_type.lower() == 'dwi':
                            data_to_bids_dwi(bids_out_dir,file,sub,scan,meta_dict_com,meta_dict_dwi="",ses="",scan_type=scan_type)
                        elif scan_type.lower() == 'fmap':
                            data_to_bids_fmap(bids_out_dir,file,sub,scan,meta_dict_com,meta_dict_fmap="",ses="",scan_type=scan_type)
                        else:
                            data_to_bids_anat(bids_out_dir,file,sub,scan,meta_dict_com,meta_dict_anat="",ses="",scan_type=scan_type)
                        if mod_found:
                            break
                            
        if mod_found:
            break
            
    if not mod_found:
        if verbose:
            print("unknown modality")
        if keep_unknown:
            scan_type = 'unknown_modality'
            scan = 'unknown'
            data_to_bids_anat(bids_out_dir,file,sub,scan,meta_dict_com,meta_dict_anat="",ses="",scan_type=scan_type)
        
    return None


