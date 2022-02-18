"""Communication with the Maptek Account broker.

The broker is responsible for talking to Maptek Account (a web service) on
our behalf and provides the necessary session and caching to make licencing
fast.

This uses Python for .NET such that .NET assemblies can be used from Python
to communicate with the broker. See https://github.com/pythonnet/pythonnet.

Warnings
--------
Vendors and clients should not develop scripts or applications against
this package. The contents may change at any time without warning.

"""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

import collections
import datetime
import os
import sys

import clr
clr.AddReference('System.Collections')

import System
import System.Collections

WorkbenchSession = collections.namedtuple(
  'WorkbenchSession',
  ['process_id', 'running_applications', 'active_application'],
  )


class Licence:
  """Represent a licence obtained via the Maptek Account broker."""

  def __init__(self, data):
    """This object typically comes from the Session object.
       You shouldn't need to construct it yourself.
    """
    self._data = data

  @property
  def license_string(self):
    return self._data.LicenseString

  @property
  def time_till_expiry(self):
    return self._data.TimeTillExpiry

  def __enter__(self):
    return self

  def __exit__(self, exception_type, exception_value, traceback):
    self._data.Dispose()
    self._data = None


class Session:
  """Represents a session with the Maptek Account broker."""

  def __init__(self, session, services):
    self.session = session.Result
    if not self.session:
      raise ValueError('You must be signed into Maptek Account.')

    self.services = services

  def disconnect(self):
    self.session.Dispose()

  def workbenches(self):
    """Return information about the Workbench instances that are currently
       running."""
    for session in self.session.WorkbenchSessions:
      yield WorkbenchSession(
        session.ProcessId,
        session.RunningApplications,
        session.ActiveApplication,
        )

  def product_information(self, name, display_name, version_label,
                          release_date, license_format):
    """Create the instance of the class required by acquire_licence().

    name : str
    display_name : str
    version_label : str
    release_date : datetime
    license_format : str
        This string comes from calling the GetFormat() function in the
        mdf_licence.dll.
    """

    # Convert from a datetime to a System.DateTimeOffset
    release_date_offset = System.DateTimeOffset.FromUnixTimeMilliseconds(
      release_date.timestamp())

    product = self.services.MaptekAccountProductInfo()
    product.Name = name
    product.DisplayName = display_name
    product.VersionLabel = version_label
    product.ReleaseDate = release_date_offset
    product.LicenseFormat = license_format
    return product

  def acquire_licence(self, product_information, feature_codes):
    """
    Parameters
    ----------
    product_information
      The production information for the product to licence.
      See self.product_information() for creating this object.

    feature_codes : list
      A list of strings with the product codes for each feature required.

    Returns
    -------
    Licence
      A licence for the given product and features.

    Raises
    ------
    ValueError
      If there was an error acquiring the licence.
    """
    # Set-up the creation parameters
    creation_parameters = self.services.LicenseCreationParams()
    creation_parameters.LicenseReturnBehavior = \
      self.services.LicenseReturnBehavior.Delayed
    creation_parameters.MinimumRequiredFeatures = \
      System.Collections.Generic.HashSet[System.String]()
    for code in feature_codes:
      creation_parameters.MinimumRequiredFeatures.Add(code)

    # Aquire the licence from the Maptek Account broker.
    licence = self.session.Licensing.GetLicenseForProduct(
      product_information,
      creation_parameters)

    no_error = self.services.MaptekAccountErrorCode.NoError
    if licence.Result.Success and licence.Result.Error == no_error:
      return Licence(licence.Result.ReturnValue)

    enum_to_name = System.Enum.Format(
      self.services.MaptekAccountErrorCode,
      licence.Result.Error,
      "g")
    raise ValueError('Unable to acquire licence: %s' % enum_to_name)

  def acquire_extend_licence(self, license_format):
    """Acquire a licence for Maptek Extend.

    Parameters
    ----------
    license_format : str
      The format of the licence to generate. This needs to be the format
      supported by the DLLs used to validate and make use of the licence.
    """
    product = self.product_information(
      name='Extend',
      display_name='Extend',
      version_label='1.3',
      license_format=license_format,
      # The release date for Maptek Extend is irrelevant to the licencing
      # system. The date provided is when Maptek was first a registered as a
      # company in Australia.
      release_date=datetime.datetime(1981, 5, 15),
      )

    return self.acquire_licence(product, ['SDK'])

def connect_to_maptek_account_broker(assembly_path=None,
                                     connection_parameters=None):
  if not assembly_path:
    assembly_path = os.path.dirname(os.path.realpath(__file__))

  interface_assembly = os.path.join(
    assembly_path, 'MaptekAccountBrokerInterfaces.dll')
  service_assembly = os.path.join(
    assembly_path, 'MaptekAccountBrokerServiceInterfaces.dll')
  main_assembly = os.path.join(
    assembly_path, 'MaptekAccountBrokerConnector.dll')

  if not os.path.isfile(main_assembly):
    # This allows the SDK to be used within Maptek's source control system.
    # This requires setup.py test or setup.py build to have already been run
    # first.
    major, minor = sys.version_info[:2]
    alternate_assembly_path = os.path.join(
      assembly_path, '..', '..', 'build',
      'lib', 'mapteksdk', 'internal')

    if os.path.isdir(alternate_assembly_path):
      main_assembly = os.path.join(
        alternate_assembly_path, 'MaptekAccountBrokerConnector.dll')
      service_assembly = os.path.join(
        alternate_assembly_path, 'MaptekAccountBrokerServiceInterfaces.dll')
      interface_assembly = os.path.join(
        alternate_assembly_path, 'MaptekAccountBrokerInterfaces.dll')
      assembly_path = alternate_assembly_path

  # Explicitly add each reference to ensure they are all loaded
  # from the SDK and not Vulcan.
  clr.AddReference(interface_assembly)
  clr.AddReference(service_assembly)
  clr.AddReference(main_assembly)
  import Maptek.AccountServices

  locator = Maptek.AccountServices.MaptekAccountServiceLocator

  binding_parameters = locator.BindingParams()
  binding_parameters.OverrideInstallSearchLocation = assembly_path
  if not locator.BindAccountServiceAssemblies(binding_parameters):
    raise EnvironmentError('Failed to bind the assemblies for the Maptek '
                           'Account services (%s)' % assembly_path)

  session_parameters = Maptek.AccountServices.SessionConnectionParams()
  if connection_parameters:
    for key, value in connection_parameters.items():
      setattr(session_parameters, key, value)

  return Session(
    locator.SessionManagement.ConnectSessionAsync(session_parameters),
    Maptek.AccountServices)
