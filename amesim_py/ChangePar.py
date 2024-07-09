
import os, sys


from amesim import *
# from ame_apy import *
# AMEInitAPI()


# # from ame_apy import *

# if 'ame_apy' not in sys.modules:
#    try:
#       from ame_apy import *
#    except ImportError:
#       print('Unable to import Simcenter Amesim API module.\nCheck the AME environment variable.')

# # Get license and initialize Simcenter Amesim Python API
# AMEInitAPI()

# # Open the AMESim file
# AMEOpenAmeFile("changeParameter.ame")

# # ==============================================================
# # ===============================================================
# # in this section, you can change the parameters. Here, you can 
# # add the variable and these variable can be linked to parameter 
# # path in AMESim
# # ===============================================================

# pres = '15.013' 		# intial pressure in Pa
# area = '15' 			# diameter in mm
# Vol = '2'               # Volume of chamber in liter.
# Tinit = '500' 			# initial temperature in the volume

# # Set Pressure source parameters
# AMESetParameterValue('press1@pn_source', '200')   
# AMESetParameterValue('area@pn_orifice', area)
# AMESetParameterValue('temp@pn_general_chamber', Tinit)
# AMESetParameterValue('temp@pn_general_chamber', Vol)
# AMESetParameterValue('U', '215')

# # ============ End of Parameter section===========================

# # Add text items

# # Save 'changeParameter.ame' system
# AMECloseCircuit(True)

# # Finalize script

# # Return license and close Simcenter Amesim Python API
# AMECloseAPI(False)
