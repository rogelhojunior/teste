"""
This module implements a script to generate a DataFrame bringing Port + Refin
data.

To execute this script simply execute:

python manage.py runscript generate_port_refin_dataframe <output-path>

<output-path> is optional, if you do not use it the report will be saved in the
path defined on OUTPUT_PATH constant.

"""

from scripts.generate_port_refin_dataframe.dataframe_generator import DataFrameGenerator
from scripts.generate_port_refin_dataframe.utils import (
    get_contracts,
    get_output_path,
    validate_path,
)


def run(*args):
    # generate output path
    output_path = get_output_path(args)

    # validate output path
    validate_path(output_path)
    print(f'Generating Port + Refin report on {output_path}')

    # query data
    queryset = get_contracts()
    print(f'{len(queryset)} contracts found')

    # create data frame from queryset
    generator = DataFrameGenerator(queryset)

    # add in100 tipo beneficio column
    generator.add_in100_tipo_beneficio()

    # add bank data column
    generator.add_bank_data_columns()

    # rename columns
    generator.rename_columns()

    # transform status number into human readable string
    generator.humanize_status()

    # remove unused columns
    generator.clean_columns()

    # add endorsement_on_dataprev column
    generator.add_endorsement_on_dataprev_column()

    # add endorsement_on_dataprev column
    generator.add_qi_tech_status_column()

    # add endorsement_on_dataprev column
    generator.add_last_tentative_columns()

    # fill pool columns
    generator.fill_pool_columns()

    # export to excel
    generator.df.to_excel(output_path, index=False)

    # display preview
    generator.display_preview()
