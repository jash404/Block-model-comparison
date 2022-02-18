"""Units and other enumrations for file operations."""
###############################################################################
#
# (C) Copyright 2020, Maptek Pty Ltd. All rights reserved.
#
###############################################################################

from enum import Enum

class Axis(Enum):
  """Enum used to choose an axis."""
  X = 0
  Y = 1
  Z = 2

class DistanceUnit(Enum):
  """Enum representing distance units supported by the Project."""
  angstrom = 301
  picometre = 316
  nanometre = 302
  micrometre = 303
  millimetre = 304
  centimetre = 305
  decimetre = 306
  metre = 307
  decametre = 308
  hectometre = 309
  kilometre = 310
  megametre = 311
  gigametre = 312
  astronomical_unit = 313
  light_year = 314
  parsec = 315
  microinch = 351
  thou = 352
  inch = 353
  feet = 354
  link = 356
  chain = 357
  yard = 358
  fathom = 359
  mile = 360
  us_survey_inch = 361
  us_survey_feet = 362
  us_survey_yard = 363
  nautical_mile = 364
