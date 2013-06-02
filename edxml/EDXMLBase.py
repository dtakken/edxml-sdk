# -*- coding: utf-8 -*-
#
#
#  ===========================================================================
# 
#                     Several commonly used Python classes.
#
#                  Copyright (c) 2010 - 2013 by D.H.J. Takken
#                          (d.h.j.takken@xs4all.nl)
#
#          This file is part of the EDXML Software Development Kit (SDK).
#
#
#  The EDXML SDK is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  The EDXML SDK is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with the EDXML SDK.  If not, see <http://www.gnu.org/licenses/>.
#
#
#  ===========================================================================

"""EDXMLBase

This module contains generic (base)classes used throughout the SDK. It contains
the following classes:

EDXMLError:                 Generic EDXML exception class
EDXMLProcessingInterrupted: Exception class signaling EDXML stream processing interruption
EDXMLBase:                  Base class for most SDK subclasses

"""

from decimal import *
import string
import sys
import re
import os

class EDXMLError(Exception):
  """Generic EDXML exception class"""
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return str(self.value)

class EDXMLProcessingInterrupted(Exception):
  """Exception for signaling that EDXML processing was aborted"""
  def __init__(self, value):
    self.value = value
  def __str__(self):
    return str(self.value)

class EDXMLBase():
  """Base class for most SDK subclasses"""

  def __init__(self):
    
    self.WarningCount = 0
    self.ErrorCount = 0
    
    # Expression used for matching SHA1 hashlinks
    self.HashlinkPattern = re.compile("^[0-9a-zA-Z]{40}$")
    # Expression used for matching string datatypes
    self.StringDataTypePattern = re.compile("string:[0-9]+:((cs)|(ci))(:[ru]+)?")
    # Expression used for matching binstring datatypes
    self.BinstringDataTypePattern = re.compile("binstring:[0-9]+(:r)?")
    # Expression used to find placeholders in event reporter strings
    self.PlaceHolderPattern = re.compile("\[\[([^\]]*)\]\]")

  def Error(self, Message):
    """Raises EDXMLError.
    Parameters:
    
    Message -- Error message
    
    """
    
    self.ErrorCount += 1
    raise EDXMLError(unicode("ERROR: " + Message).encode('utf-8'))

  def Warning(self, Message):
    """Prints a warning to sys.stderr.
    Parameters:
    
    Message -- Warning message
    
    """
    self.WarningCount += 1
    sys.stderr.write(unicode("WARNING: " + Message + "\n").encode('utf-8'))

  def GetWarningCount(self):
    """Returns the number of warnings generated"""
    return self.WarningCount
    
  def GetErrorCount(self):
    """Returns the number of errors generated"""
    return self.ErrorCount
  
  def ValidateDataType(self, ObjectType, DataType):
    """Validate a data type.
    Parameters:
    
    ObjectType -- Object type having specified data type
    DataType   -- The data type
    
    calls self.Error when datatype is invalid.
    
    """

    SplitDataType = DataType.split(':')
    
    if SplitDataType[0] == 'enum':
      if len(SplitDataType) > 1:
        return
    elif SplitDataType[0] == 'timestamp':
      if len(SplitDataType) == 1:
        return
    elif SplitDataType[0] == 'ip':
      if len(SplitDataType) == 1:
        return
    elif SplitDataType[0] == 'hashlink':
      if len(SplitDataType) == 1:
        return
    elif SplitDataType[0] == 'boolean':
      if len(SplitDataType) == 1:
        return
    elif SplitDataType[0] == 'geo':
      if len(SplitDataType) == 2:
        if SplitDataType[1] == 'point':
          return
    elif SplitDataType[0] == 'number':
      if len(SplitDataType) >= 2:
        if SplitDataType[1] in ['tinyint', 'smallint', 'mediumint', 'int', 'bigint', 'float', 'double']:
          if len(SplitDataType) == 3:
            if SplitDataType[1] == 'unsigned':
              return
          else:
            return
        elif SplitDataType[1] == 'decimal':
          if len (SplitDataType) >= 4:
            try:
              int(SplitDataType[2])
              int(SplitDataType[3])
            except:
              pass
            else:
              if int(SplitDataType[3]) > int(SplitDataType[2]):
                self.Error("Invalid Decimal: " + DataType)
              if len (SplitDataType) > 4:
                if len (SplitDataType) == 5:
                  if SplitDataType[4] == 'signed':
                    return
              else:
                return
        elif SplitDataType[1] == 'hex':
          if len(SplitDataType) > 3:
            try:
              HexLength        = int(SplitDataType[2])
              DigitGroupLength = int(SplitDataType[3])
            except:
              pass
            else:
              if HexLength % DigitGroupLength != 0:
                self.Error("Length of hex datatype is not a multiple of separator distance: " + DataType)
              if len(SplitDataType[4]) == 0 and len(SplitDataType) == 6:
                # This happens if the colon ':' is used as separator
                return
          else:
            return
    elif SplitDataType[0] == 'string':
      if re.match(self.StringDataTypePattern, DataType):
        return
    elif SplitDataType[0] == 'binstring':
      if re.match(self.BinstringDataTypePattern, DataType):
        return
    
    self.Error("EDXMLBase::ValidateDataType: Object type %s has an unsupported data type: %s" % (( ObjectType, DataType )) )

  def ValidateObject(self, Value, ObjectTypeName, DataType):
    """Validate an object value.
    Parameters:
    
    Value            -- Object value
    ObjectTypeName   -- Object type
    DataType         -- Data type of object
    
    calls self.Error when value is invalid.
    
    """

    ObjectDataType = DataType.split(':')

    if ObjectDataType[0] == 'timestamp':
      try:
        float(Value)
      except ValueError:
        self.Error("Invalid timestamp '%s' of object type %s." % (( str(Value), ObjectTypeName )))
    elif ObjectDataType[0] == 'number':
      if ObjectDataType[1] == 'decimal':
        if len(ObjectDataType) < 5:
          # Decimal is unsigned.
          if Value < 0:
            self.Error("Unsigned decimal value '%s' of object type %s is negative." % (( str(Value), ObjectTypeName )))
      elif ObjectDataType[1] == 'hex':
        if len(ObjectDataType) > 3:
          HexSeparator = ObjectDataType[5]
          if len(HexSeparator) == 0:
            HexSeparator = ':'
            Value = ''.join(c for c in Value if c != HexSeparator)
        try:
          Value.decode("hex")
        except:
          self.Error("Invalid hexadecimal value '%s' of object type %s." % (( str(Value), ObjectTypeName )))
      elif ObjectDataType[1] == 'float' or ObjectDataType[1] == 'double':
        try:
          float(Value)
        except ValueError:
          self.Error("Invalid number '%s' of object type %s." % (( str(Value), ObjectTypeName )))
        if len(ObjectDataType) < 3:
          # number is unsigned.
          if Value < 0:
            self.Error("Unsigned float or double value '%s' of object type %s is negative." % (( str(Value), ObjectTypeName )))
      else:
        if len(ObjectDataType) < 3:
          # number is unsigned.
          if Value < 0:
            self.Error("Unsigned integer value '%s' of object type %s is negative." % (( str(Value), ObjectTypeName )))
    elif ObjectDataType[0] == 'geo':
      if ObjectDataType[1] == 'point':
        # This is the only option at the moment.
        pass
    elif ObjectDataType[0] == 'string':
      # First, we check if value is a unicode
      # string. If not, we convert it to unicode.
      if not isinstance(Value, unicode):
        if not isinstance(Value, str):
          sys.stderr.write("EDXMLBase::ValidateObject: WARNING: Expected a string, but passed value is no string: '%s'" % str(Value) )
          Value = str(Value)
        try:
          Value = Value.decode('utf-8')
        except UnicodeDecodeError:
          # String is not proper UTF8. Lets try to decode it as Latin1
          try:
            Value = Value.decode('latin-1').encode('utf-8')
          except:
            self.Warning("EDXMLBase::ValidateObject: Failed to convert value to unicode: '%s'. Some characters were replaced by the Unicode replacement character." % repr(Value) )

      # Check if data type matches regexp pattern
      if re.match(self.StringDataTypePattern, DataType) == False:
        self.Error("EDXMLBase::ValidateObject: Invalid string data type: %s" % DataType)

      # Check length of object value
      StringLength = int(ObjectDataType[1])
      if StringLength > 0 and len(Value) > StringLength:
        self.Error("EDXMLBase::ValidateObject: string too long for object type %s: '%s'" % (( ObjectTypeName, Value )))

      # Check character set of object value
      if len(ObjectDataType) < 4 or 'u' not in ObjectDataType[3]:
        # String should only contain latin1 characters.
        try:
          unicode(Value).encode('latin1')
        except:
          self.Error("EDXMLBase::ValidateObject: string of latin1 objecttype %s contains unicode characters: %s" % (( ObjectTypeName, Value )))
    elif ObjectDataType[0] == 'binstring':
      # Check if data type matches regexp pattern
      if re.match(self.BinstringDataTypePattern, DataType) == False:
        self.Error("EDXMLBase::ValidateObject: Invalid binstring data type: %s" % DataType)
      if ObjectDataType[1] > 0 and len(Value) > ObjectDataType[1]:
          self.Error("EDXMLBase::ValidateObject: binstring too long for object type %s: '%s'" % (( ObjectTypeName, Value )))
    elif ObjectDataType[0] == 'hashlink':
      if re.match(self.HashlinkPattern, Value) == False:
        self.Error("EDXMLBase::ValidateObject: Invalid hashlink: '%s'" % str(Value) )
    elif ObjectDataType[0] == 'ip':
      SplitIp = Value.split('.')
      if len(SplitIp) != 4:
        self.Error("EDXMLBase::ValidateObject: Invalid IP address: '%s'" % str(Value) )
      for SplitIpPart in SplitIp:
        try:
          if not 0 <= int(SplitIpPart) <= 255:
            self.Error("EDXMLBase::ValidateObject: Invalid IP address: '%s'" % str(Value) )
        except ValueError:
            self.Error("EDXMLBase::ValidateObject: Invalid IP address: '%s'" % str(Value) )
    elif ObjectDataType[0] == 'boolean':
      ObjectString = Value.lower()
      if ObjectString != 'true' and ObjectString != 'false':
        self.Error("EDXMLBase::ValidateObject: Invalid boolean: '%s'" % str(Value) )
    elif ObjectDataType[0] == 'enum':
      if not Value in ObjectDataType[1:]:
        self.Error("EDXMLBase::ValidateObject: Invalid value for enum data type: '%s'" % str(Value) )
    else:
      self.Error("EDXMLBase::ValidateObject: Invalid data type: '%s'" % str(DataType) )

  def NormalizeObject(self, Value, DataType):
    """Normalize an object value to a unicode string"""
    if DataType[0] == 'timestamp':
      return u'%.6f' % Decimal(Value)
    elif DataType[0] == 'number':
      if DataType[1] == 'decimal':
        DecimalPrecision = DataType[3]
        return unicode('%.' + DecimalPrecision + 'f') % Decimal(Value)
      elif DataType[1] in [ 'tinyint', 'smallint', 'mediumint', 'int', 'bigint']:
        return u'%d' % int(Value)
      else:
        return u'%f' % float(Value)
    elif DataType[0] == 'ip':
      try:
        Octets = Value.split('.')
      except Exception as Except:
        self.Error("NormalizeObject: Invalid IP: '%s': %s" % (( Value, Except )))
      else:
        try:
          return unicode('%d.%d.%d.%d' % (( int(Octets[0]), int(Octets[1]), int(Octets[2]), int(Octets[3]) ))  )
        except:
          self.Error("NormalizeObject: Invalid IP: '%s'" % Value)

    elif DataType[0] == 'string':

      if not isinstance(Value, unicode):
        if not isinstance(Value, str):
          sys.stderr.write("NormalizeObject: WARNING: Expected a string, but passed value is no string: '%s'" % str(Value) )
          Value = unicode(Value)
        try:
          Value = Value.decode('utf-8')
        except UnicodeDecodeError:
          # String is not proper UTF8. Lets try to decode it as Latin1
          try:
            Value = Value.decode('latin-1').encode('utf-8').decode('utf-8')
          except:
            self.Error("NormalizeObject: Failed to convert string object to unicode: '%s'." % repr(Value) )

      if DataType[2] == 'ci':
        Value = Value.lower()
      return unicode(Value)
    elif DataType[0] == 'boolean':
      return unicode(Value.lower())
    else:
      return unicode(Value )
