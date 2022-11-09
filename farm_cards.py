########
# Name:         Farm Card Calculations
# Author:       Josh Carlson, Kendall County IL
# Last Updated: 07-Oct-2022
# Description:  A script to calculate farmland features for import into Devnet
# Output:       A .txt file
########

def calc_farms(pins=None, pin_file=None, out_file=None, errors='warn', acre_tolerance=0.001):

    """
    Calculates farm card import values for set of input PINs.

        Parameters:
            pins (str): A string of one to many PINs. If this parameter is set, it will override any `pin_file`.
            pin_file (str): A path to a text-based file with PINs in it.
            out_file (str): A path to the desired output file. Defaults to the desktop if not otherwise specified.
            errors (str): How the function should handle any errors. Default 'warn' will print messages but take no other action. Additional valid options:
                - halt: Stop the script when an error is encountered
                - write: Write error messages to separate file
                - ignore: No errors will be reported
            acre_tolerance (float): A percentage. When the output acreage does not match the input, differences under this threshold will be scaled up or down to meet the input acreage.
    """

    ## Modules
    import geopandas as gp
    import pandas as pd
    import numpy as np
    import requests
    from pathlib import Path
    from datetime import datetime
    import re

    # Suppress constant warnings; these come from GeoPandas, not in our control
    pd.options.mode.chained_assignment = None

    ## Figures
    def gen_figure(p_df, s_df, l_df, filename):

        import matplotlib.pyplot as plt

        fig, axs = plt.subplots(1,3, figsize=(18,8), sharex=True, sharey=True)

        p_df.plot(column='pin_dashless', ax=axs[0])
        s_df.plot(column='musym', ax=axs[1])
        l_df.plot(column='landuse_type', ax=axs[2])

        axs[0].set_title('Parcels')
        axs[1].set_title('Soils')
        axs[2].set_title('Landuse')

        fig.savefig(filename)

    ## Error Function
    def farm_error(msg):

        if errors == 'warn':
            print(' '.join(msg.split(',')))
        elif errors == 'write':
            with open('./errors.csv', 'a') as e:
                e.write(f'\n{msg}')
        elif errors == 'halt':
            raise ValueError(msg)

    # Check to see if correct values passed to params
    if errors not in ['warn', 'write', 'halt', 'ignore']:
        raise ValueError(f'errors value of "{errors}" is incorrect. Please specify one of: warn, ignore, halt, or write')

    ## Globals -- Change these as needed
    # Spatial reference for layers
    sr = "{'wkid': 3435}"

    # Parcels REST service
    parcels_url = 'https://maps.co.kendall.il.us/server/rest/services/Hosted/Current_Cadastral_Features/FeatureServer/1/query?'

    # SSURGO Soils REST service
    soils_url = 'https://maps.co.kendall.il.us/server/rest/services/Hosted/Assessor_Soils/FeatureServer/0/query?'

    # Landuse REST service
    landuse_url = 'https://maps.co.kendall.il.us/server/rest/services/Hosted/Assessor_Landuse/FeatureServer/0/query?'

    # Prepare default output
    if not out_file:
        out_file = Path.expanduser(Path(f"./output/farms_{datetime.now().strftime('%Y%m%d-%H%M')}.txt"))

    # If specifically set to 'write', create fresh file
    if errors == 'write':
        with open('./errors.csv', 'w') as e:
            e.write('PIN,error,num')
        
    ## Drop any existing file by same name
    if Path.exists(out_file):
        print('Output file already exists. Removing!')
        Path(out_file).unlink()
    Path.touch(out_file)
    print('Good to go!')

    ## Warnings start at False
    warnings = False

    ## Get PINs
    # Read file if `pins` parameter not stated
    if not pins:
        with open(pin_file) as pfile:
            pins = pfile.read()

    # Find all valid PINs in string, convert to list
    pin_patt = re.compile(r'\d{2}-?\d{2}-?\d{3}-?\d{3}')
    pin_list = list(map(lambda x: x.replace('-', ''), re.findall(pin_patt, pins)))

    # Dedupe list
    pin_list = list(dict.fromkeys(pin_list))
    

    ### Iterate over pin_list and calculate per parcel, append to output file
    n = 0

    while n < len(pin_list):

        ## Parcels DF
        # Request parameters
        parcels_params = {
            'where': f"pin_dashless = '{pin_list[n]}'",
            'outFields': 'gross_acres, pin_dashless',
            'outSR': sr,
            'f': 'geojson'
        }

        # Get parcels
        parcel = requests.get(parcels_url, parcels_params)

        # Check that query returned a shape
        p_dict = parcel.json()

        if len(p_dict['features']) == 0:
            
            farm_error(f"{pin_list[n]},query returned no features,")
            warnings = True
            n += 1
            continue

        # Convert to geodataframe
        p_df = gp.read_file(parcel.text)
        p_df['calc_area'] = p_df.area

        # Check to see that parcels have an acreage listed
        if p_df.loc[0,'gross_acres'] == 0 or not p_df.loc[0,'gross_acres']:
            farm_error(f"{pin_list[n]},has no acreage listed,0")
            warnings = True
            n += 1
            continue

        # Spatial Filter
        bbox = ','.join([str(i) for i in p_df.total_bounds])

        # Params
        farm_params = {
            'where': '1=1',
            'outFields': '*',
            'returnGeometry': True,
            'geometryType': 'esriGeometryEnvelope',
            'geometry': bbox,
            'spatialRel': 'esriSpatialRelIntersects',
            'outSR': sr,
            'f': 'geojson'
        }

        # Soils
        soils = requests.get(soils_url, farm_params)
        s_df = gp.read_file(soils.text)
        s_df.loc[:, 'slope'].fillna('', inplace=True)

        # Landuse
        landuse = requests.get(landuse_url, farm_params)

        l_df = gp.read_file(landuse.text)

        ## Overlay Data, Tidy Up
        df = gp.overlay(p_df, s_df, how='intersection')
        df = gp.overlay(df, l_df, how='intersection')

        # Remove unwanted columns
        keepers = [
            'gross_acres',
            'gis_acres',
            'calc_area',
            'pin_dashless',
            'soil_type',
            'slope',
            'landuse_type',
            'geometry'
        ]

        df.drop(columns=[c for c in df if c not in keepers], inplace=True)

        # Calculate part acres
        df['part_acres'] = df.area / df['calc_area'] * df['gross_acres']

        # Drop other columns
        df.drop(columns=['calc_area'], inplace=True)

        # LU to string
        df.loc[:, 'landuse_type'] = '0' + df['landuse_type'].astype('str')

        ## Finish up acreage
        # Aggregate
        out_cols = ['pin_dashless', 'soil_type', 'slope', 'landuse_type']

        aggs = {
            'soil_type':'first',
            'slope':'first',
            'landuse_type':'first',
            'pin_dashless':'first',
            'gross_acres':'max',
            'part_acres':'sum'
        }

        df = df.groupby(by=out_cols, as_index=False).agg(aggs).reset_index(drop=True)

        ## Check acreage sums
        qc = df.groupby('pin_dashless').agg({'gross_acres':'max', 'part_acres':'sum'}).reset_index()
        qc['diff'] = qc['gross_acres'] - round(qc['part_acres'], 4)
        qc['pct_off'] = qc['gross_acres'] / qc['part_acres']

        ## Single out measurable differences
        outliers = qc.query('diff > 0')

        if len(outliers) > 0 and errors != 'ignore':

            # Compare against tolerance; scale if under
            if abs(1 - qc.loc[0,'pct_off']) <= acre_tolerance:
                
                df.loc[:,'part_acres'] = df.loc[:,'part_acres'] * qc.loc[0,'pct_off']
                

            else:
                farm_error(f"{qc.loc[0,'pin_dashless']},has acreage mismatch, {qc.loc[0,'diff']:f}")
                warnings = True

                gen_figure(p_df, s_df, l_df, qc.loc[0,'pin_dashless'])

                n += 1
                continue

        # Round of to 4 decimals
        df.loc[:, 'part_acres'] = round(df.loc[:, 'part_acres'], 4)

        # Drop 0s
        df = df[df.loc[:, 'part_acres'] > 0]

        # Remove extra fields
        df.drop(columns=['gross_acres'], inplace=True)

        df.to_csv(out_file, sep='\t', header=False, index=False, mode='a')

        n += 1

    if warnings:
        print(f'Completed, but with warnings. Check {"error file" if errors == "write" else "terminal messages"} for more deatils.')
    else:
        print('Completed!')
