# -*- coding: utf-8 -*-
#
#
#  ===========================================================================
# 
#                        EDXMLDefinitions Python class
#
#                  Copyright (c) 2010 - 2014 by D.H.J. Takken
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
#  ===========================================================================



"""EDXMLDefinitions

This module contains the EDXMLDefinitions class, which manages
information from EDXML <definitions> sections.

"""

import hashlib
from decimal import *
from EDXMLBase import *
from lxml import etree
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesImpl

class EDXMLDefinitions(EDXMLBase):
  """Class for managing information from EDXML <definitions> sections.
  
  This class is used for managing definitions of event types, object
  types and sources from EDXML files. It is used for storing parsed
  definitions, querying definitions, and merging definitions from
  various EDXML files. It can be used to store <definitions> sections
  from multiple EDXML streams in succession, which results in the
  definitions from all streams being merged together. During the merge,
  the definitions are automatically checked for compatibility with
  previously stored definitions. The EDXMLError exception is raised when
  problems are detected.
 
  The class also offers methods to generate EDXML <definitions> sections
  from the stored definitions, or generate (partial) XSD and RelaxNG
  schemas which can be used for validation of EDXML files.
  
  """
  
  def __init__(self):
    
    self.SourceIDs = {}
    self.SourceURLs = {}
    self.EventTypes = {}
    self.ObjectTypes = {}
    self.ObjectTypeEventTypes = {}
    self.EventTypeClasses = {}
    self.RelationPredicates = set()
    self.RequiredObjectTypes = set()
    self.EntityProperties = {}
    self.CompiledObjectTypePatterns = {}

    # These arrays hold names of event types,
    # properties and sources, in the exact
    # order they were encountered
    # in the EDXML stream.
    self.EventTypeNames = []
    self.PropertyNames = {}
    self.PropertyRelations = {}
    self.ObjectTypeNames = []
    self.Sources = []

    # Used for XSD generation
    self.XSD = {'xs': 'http://www.w3.org/2001/XMLSchema'}
    
    self.SchemaRelaxNG = None
    self.SchemaXSD = None

    self.KnownFormatters = ['TIMESPAN', 'DATE', 'DATETIME', 'FULLDATETIME', 'WEEK', 'MONTH', 'YEAR', 'DURATION',
                            'LATITUDE', 'LONGITUDE', 'BYTECOUNT', 'CURRENCY', 'COUNTRYCODE', 'FILESERVER', 
                            'BOOLEAN_STRINGCHOICE', 'BOOLEAN_ON_OFF', 'BOOLEAN_IS_ISNOT', 'EMPTY']
                            
    self.ReporterPlaceholderPattern = re.compile('\\[\\[([^\\]]*)\\]\\]')
  
    # Some validation patterns
  
    self.SimpleNamePattern    = re.compile("^[a-z0-9-]*$")
    self.DisplayNamePattern   = re.compile("^[ a-zA-Z0-9]+/[ a-zA-Z0-9]+$")
    self.TrueFalsePattern     = re.compile("^(true)|(false)$")
    self.DecimalPattern       = re.compile("^[0-9.]+$")
    self.SourceDatePattern    = re.compile("^[0-9]{8}$")
    self.MergeOptions         = re.compile("^(drop)|(add)|(replace)|(min)|(max)|(match)$")
    self.RelationTypePattern  = re.compile("^(intra|inter|parent|child|other):.+")
    self.FuzzyMatchingPattern = re.compile("^(none)|(phonetic)|(\[[0-9]{1,2}:\])|(\[:[0-9]{1,2}\])$")
    self.DataTypePattern      = re.compile("^(boolean)|(timestamp)|(ip)|(hashlink)|(" + \
                                             "(number:(" + \
                                                 "((((tiny)|(small)|(medium)|(big))?int)|(float)|(double))(:signed)?" + \
                                               "))|(number:decimal:[0-9]+:[0-9]+(:signed)?)|(number:hex:[0-9]+(:[0-9]+:.)?)|(enum:.*)|(" + \
                                             "geo:(" + \
                                                 "(point)" + \
                                               "))|(string:(" + \
                                                 "[0-9]+:((cs)|(ci))(:[ru]+)?" + \
                                               "))|(binstring:(" + \
                                                 "[0-9]+(:r)?" + \
                                               "))" + \
                                           ")$")
 
    # This dictionary contains constraints of attribute values of EDXML
    # entities, like eventtype, objecttype, property, etc. The restrictions
    # are extracted from the RelaxNG schema.
    
    self.EDXMLEntityAttributes = {
      'eventtype': {
        'name':           {'mandatory': True,  'length': 40,   'pattern': self.SimpleNamePattern},
        'display-name':   {'mandatory': False, 'length': 64,   'pattern': self.DisplayNamePattern, 'default': '/'},
        'description':    {'mandatory': True,  'length': 128,  'pattern': None},
        'classlist':      {'mandatory': True,  'length': None, 'pattern': None},
        'reporter-short': {'mandatory': True,  'length': None, 'pattern': None},
        'reporter-long':  {'mandatory': True,  'length': None, 'pattern': None}
      },
      'property': {
        'name':              {'mandatory': True,  'length': 64,   'pattern': self.SimpleNamePattern},
        'description':       {'mandatory': True,  'length': 128,  'pattern': None},
        'similar':           {'mandatory': False, 'length': 64,   'pattern': None},
        'object-type':       {'mandatory': True,  'length': 40,   'pattern': self.SimpleNamePattern},
        'unique':            {'mandatory': False, 'length': None, 'pattern': self.TrueFalsePattern, 'default': 'false'},
        'merge':             {'mandatory': False, 'length': None, 'pattern': self.MergeOptions,     'default': 'drop'},
        'defines-entity':    {'mandatory': False, 'length': None, 'pattern': self.TrueFalsePattern, 'default': 'false'},
        'entity-confidence': {'mandatory': False, 'length': None, 'pattern': self.DecimalPattern,   'default': '0'}
      },
      'relation': {
        'property1':   {'mandatory': True,  'length': 64,   'pattern': self.SimpleNamePattern},
        'property2':   {'mandatory': True,  'length': 64,   'pattern': self.SimpleNamePattern},
        'directed':    {'mandatory': False, 'length': None, 'pattern': self.TrueFalsePattern, 'default': 'true'},
        'description': {'mandatory': True,  'length': 255,  'pattern': None},
        'type':        {'mandatory': True,  'length': 32,   'pattern': self.RelationTypePattern},
        'confidence':  {'mandatory': True,  'length': None, 'pattern': self.DecimalPattern}
      },
      'objecttype': {
        'name':              {'mandatory': True,  'length': 40,   'pattern': self.SimpleNamePattern},
        'display-name':      {'mandatory': False, 'length': 64,   'pattern': self.DisplayNamePattern, 'default': '/'},
        'description':       {'mandatory': True,  'length': 128,  'pattern': None},
        'fuzzy-matching':    {'mandatory': False, 'length': None, 'pattern': self.FuzzyMatchingPattern, 'default': 'none'},
        'compress':          {'mandatory': False, 'length': None, 'pattern': self.TrueFalsePattern, 'default': 'false'},
        'enp':               {'mandatory': False, 'length': None, 'pattern': None, 'default': '0'},
        'regexp':            {'mandatory': False, 'length': 128,  'pattern': None, 'default': '[\s\S]*'},
        'data-type':         {'mandatory': True,  'length': None, 'pattern': self.DataTypePattern}
      },
      'source': {
        'source-id':        {'mandatory': True,  'length': None,  'pattern': None},
        'url':              {'mandatory': True,  'length': None,  'pattern': None},
        'date-acquired':    {'mandatory': True,  'length': None,  'pattern': self.SourceDatePattern},
        'description':      {'mandatory': True,  'length': 128,   'pattern': None},
      },
    }
  
    EDXMLBase.__init__(self)
  
  def SourceIdDefined(self, SourceId):
    """Returns boolean indicating if given Source ID exists."""
    return SourceId in self.SourceIDs.keys()
  
  def EventTypeDefined(self, EventTypeName):
    """Returns boolean indicating if given event type is defined."""
    return EventTypeName in self.EventTypes
  
  def PropertyDefined(self, EventTypeName, PropertyName):
    """Returns boolean indicating if given property is defined."""
    return PropertyName in self.EventTypes[EventTypeName]['properties']
      
  def ObjectTypeDefined(self, ObjectTypeName):
    """Returns boolean indicating if given object type is defined."""
    return ObjectTypeName in self.ObjectTypes
  
  def RelationDefined(self, EventTypeName, Property1Name, Property2Name):
    """Returns boolean indicating if given property relation is defined."""
    RelationId = Property1Name + ' -> ' + Property2Name
    return RelationId in self.EventTypes[EventTypeName]['relations']
  
  def GetRelationPredicates(self):
    """Returns list of known relation predicates."""
    return list(self.RelationPredicates)
  
  def EventTypeIsUnique(self, EventTypeName):
    """Returns a boolean indicating if given eventtype is unique or not."""
    return self.EventTypes[EventTypeName]['unique']

  def PropertyIsUnique(self, EventTypeName, PropertyName):
    """Returns a boolean indicating if given property is unique or not."""
    return PropertyName in self.EventTypes[EventTypeName]['unique-properties']

  def GetUniqueProperties(self, EventTypeName):
    """Returns a list of names of unique properties"""
    return self.EventTypes[EventTypeName]['unique-properties']

  def GetMandatoryObjectProperties(self, EventTypeName):
    """Returns a list of names of properties which must have an object"""
    return self.EventTypes[EventTypeName]['mandatory-properties']

  def GetSingletonObjectProperties(self, EventTypeName):
    """Returns a list of names of properties which cannot have multiple objects"""
    return self.EventTypes[EventTypeName]['singleton-properties']

  def PropertyDefinesEntity(self, EventTypeName, PropertyName):
    """Returns boolean indicating if property of given event type is an entity identifier."""
    return PropertyName in self.EntityProperties[EventTypeName]
  
  def PropertyInRelation(self, EventTypeName, PropertyName):
    """Returns a boolean indicating if given
    property of specified event type is involved
    in any defined property relation."""
    return PropertyName in self.EventTypes[EventTypeName]['related-properties']
  
  def GetSourceURLs(self):
    """Returns an ordered list of all parsed
    source URLs. The order as they
    appeared in the EDXML stream is preserved."""
    return self.SourceURLs.keys()

  def GetSourceIDs(self):
    """Returns a list of all known source ID"""
    return self.Sources
    
  def GetSourceId(self, Url):
    """Returns the ID of event source having specified URL"""
    return self.SourceURLs[Url]['source-id']

  def GetEventTypeNames(self):
    """Returns a list of all known
    event type names. The order as they
    appeared in the EDXML stream is preserved."""
    return self.EventTypeNames
    
  def GetEventTypeAttributes(self, EventTypeName):
    """Returns a dictionary containing all
    attributes of requested event type."""
    return self.EventTypes[EventTypeName]['attributes']
    
  def GetEventTypeParent(self, EventTypeName):
    """Returns a dictionary containing all
    attributes of the parent of requested eventtype.
    Returns empty dictionary when event type has no
    defined parent."""
    if 'parent' in self.EventTypes[EventTypeName]:
      return self.EventTypes[EventTypeName]['parent']
    else:
      return {}
  
  def GetEventTypeParentMapping(self, EventTypeName):
    """Returns a dictionary containing all property
    names of the event type that map to a parent property.
    The value of each key corresponds to the name of the
    parent property that the child property maps to.
    Returns empty dictionary when event type has no
    defined parent."""
    if 'parent' in self.EventTypes[EventTypeName]:
      return self.EventTypes[EventTypeName]['parentmapping']
    else:
      return {}
  
  def GetEventTypesHavingObjectType(self, ObjectTypeName):
    """Returns a list of event type names having specified object type."""
    if not ObjectTypeName in self.ObjectTypeEventTypes:
      return []
    else:
      return list(self.ObjectTypeEventTypes[ObjectTypeName])
    
  def GetEventTypeNamesInClass(self, ClassName):
    """Returns a list of event type names that belong to specified class."""
    return list(self.EventTypeClasses[ClassName])
    
  def GetEventTypeNamesInClasses(self, ClassNames):
    """Returns a list of event type names that belong to specified list of classes."""
    EventTypeNames = set()
    for ClassName in ClassNames:
      for EventTypeName in self.EventTypeClasses[ClassName]:
        EventTypeNames.add(EventTypeName)
    return list(EventTypeNames)
    
  def GetObjectTypeAttributes(self, ObjectTypeName):
    """Returns a dictionary containing all attributes of specified object type."""
    return self.ObjectTypes[ObjectTypeName]
    
  def GetEventTypeProperties(self, EventTypeName):
    """Returns a list of all property names
    of given event type. The order as they
    appeared in the EDXML stream is preserved."""
    return self.PropertyNames[EventTypeName]
    
  def GetEventTypePropertyRelations(self, EventTypeName):
    """Returns a list of all IDs of property relations
    in given event type. The order as they
    appeared in the EDXML stream is preserved."""
    return self.PropertyRelations[EventTypeName]
  
  def GetPropertyRelationAttributes(self, EventTypeName, RelationId):
    """Returns a dictionary containing all attributes of requested object type."""
    return self.EventTypes[EventTypeName]['relations'][RelationId]
  
  def GetObjectTypeNames(self):
    """Returns a list of all known object type names.
    The order as they appeared in the EDXML stream is preserved."""
    return self.ObjectTypeNames

  def GetSourceURLProperties(self, Url):
    """Returns dictionary containing source attributes of the source specified by given URL."""
    return self.SourceURLs[Url]

  def GetSourceIdProperties(self, SourceId):
    """Returns dictionary containing source attributes of the source specified by given Source ID."""
    return self.SourceURLs[self.SourceIDs[SourceId]]
  
  def ObjectTypeRequiresUnicode(self, ObjectTypeName):
    """Returns True when given string object type requires
    unicode characters, return False otherwise."""
    ObjectDataType = self.ObjectTypes[ObjectTypeName]['data-type'].split(':')
    if len(ObjectDataType) < 4 or 'u' not in ObjectDataType[3]:
      return False
    else:
      return True
    
  def GetPropertyObjectType(self, EventTypeName, PropertyName):
    """Return the name of the object type of specified event property."""
    if EventTypeName in self.EventTypes:
      if PropertyName in self.EventTypes[EventTypeName]['properties']:
        ObjectType = self.EventTypes[EventTypeName]['properties'][PropertyName]['object-type']
        return ObjectType
      else:
        self.Error('Event type %s has no property named "%s"' % (( str(EventTypeName), str(PropertyName) )) )
    else:
      self.Error('Unknown event type %s' % str(EventTypeName) )

  def GetPropertyAttributes(self, EventTypeName, PropertyName):
    """Return dictionary of attributes of specified event property."""
    return self.EventTypes[EventTypeName]['properties'][PropertyName]

  def GetObjectTypeDataType(self, ObjectTypeName):
    """Return the data type of given object type."""
    return self.ObjectTypes[ObjectTypeName]['data-type']

  def AddEventType(self, EventTypeName, Attributes):
    """Add an event type to the collection of event type
    definitions. If an event type definition with the same
    name exists, it will be checked for consistency with
    the existing definition.
    
    Parameters:
    
    EventTypeName -- Name of event type
    Attributes    -- Dictionary holding the attributes of the 'eventtype' tag.
    
    """
    if EventTypeName in self.EventTypes:
      # Event type definition was encountered before.
      self.CheckEdxmlEntityConsistency('eventtype', EventTypeName, self.EventTypes[EventTypeName]['attributes'], Attributes)
    else:
      # New event type
      self.AddNewEventType(EventTypeName, Attributes)
  
  def SetEventTypeParent(self, EventTypeName, Attributes):
    """Configure a parent of specified event type.
    
    Parameters:
    
    EventTypeName -- Name of event type
    Attributes    -- Dictionary holding the attributes of the 'parent' tag.
    
    """
    
    if 'parent' in self.EventTypes[EventTypeName]:
      # Parent definition was encountered before.
      self.CheckEdxmlEntityConsistency('parent', Attributes['eventtype'], self.EventTypes[EventTypeName]['parent'], Attributes)
    else:
      # New parent definition
      self.SetNewEventTypeParent(EventTypeName, Attributes)
  
  def AddProperty(self, EventTypeName, PropertyName, Attributes):
    """Add a property to the collection of property
    definitions. If a property definition with the same
    name exists, it will be checked for consistency with
    the existing definition.
    
    Parameters:
    
    EventTypeName -- Name of event type
    PropertyName  -- Name of property
    Attributes    -- Dictionary holding the attributes of the 'property' tag.
    
    """
    if PropertyName in self.EventTypes[EventTypeName]['properties']:
      # Property definition was encountered before.
      self.CheckEdxmlEntityConsistency('property', PropertyName, self.EventTypes[EventTypeName]['properties'][PropertyName], Attributes)
    else:
      # New property
      self.AddNewProperty(EventTypeName, PropertyName, Attributes)
        
  def AddRelation(self, EventTypeName, Property1Name, Property2Name, Attributes):
    """Add a relation to the collection of relation
    definitions. If a relation definition with the same
    properties exists, it will be checked for consistency with
    the existing definition.
    
    Parameters:
    
    EventTypeName -- Name of event type
    Property1Name -- Name of property 1
    Property2Name -- Name of property 2
    Attributes    -- Dictionary holding the attributes of the 'relation' tag.
    
    """
    RelationId = Property1Name + ' -> ' + Property2Name
    if RelationId in self.EventTypes[EventTypeName]['relations']:
      # Relation definition was encountered before.
      self.CheckEdxmlEntityConsistency('relation', RelationId, self.EventTypes[EventTypeName]['relations'][RelationId], Attributes)
    else:
      self.AddNewRelation(EventTypeName, RelationId, Property1Name, Property2Name, Attributes)
      
  def AddObjectType(self, ObjectTypeName, Attributes, WarnNotUsed = True):
    """Add an object type to the collection of object type
    definitions. If an object type definition with the same
    name exists, it will be checked for consistency with
    the existing definition.
    
    Parameters:
    
    ObjectTypeName -- Name of event type
    Attributes     -- Dictionary holding the attributes of the 'objecttype' tag.
    WarnNotUsed    -- Generate a warning if no property uses the object type (optional, default is True)
    
    """
    if WarnNotUsed:
      if not ObjectTypeName in self.RequiredObjectTypes:
        self.Warning("Object type %s was defined, but it is not used." % ObjectTypeName )
    if ObjectTypeName in self.ObjectTypes:
      # Object type was defined before
      self.CheckEdxmlEntityConsistency('objecttype', ObjectTypeName, self.ObjectTypes[ObjectTypeName], Attributes)
    else:
      # New object type
      self.AddNewObjectType(ObjectTypeName, Attributes)
      
  def AddSource(self, SourceUrl, Attributes):
    """Add a source to the collection of event source
    definitions. If a source definition with the same
    URL exists, it will be checked for consistency with
    the existing definition.
    
    Parameters:
    
    SourceUrl   -- URL of event source
    Attributes  -- Dictionary holding the attributes of the 'source' tag.
    
    """
    SourceId = Attributes['source-id']
    self.SourceIDs[SourceId] = SourceUrl
    if SourceUrl in self.SourceURLs.keys():
      self.CheckEdxmlEntityConsistency('source', SourceUrl, self.SourceURLs[SourceUrl], Attributes)
    else:
      self.Sources.append(SourceId)
      self.AddNewSource(SourceUrl, Attributes)
  
  # Internal use only.
  def AddNewEventType(self, EventTypeName, Attributes):
    
    self.EventTypeNames.append(EventTypeName)
    self.PropertyNames[EventTypeName] = []
    self.EntityProperties[EventTypeName] = set()
    self.PropertyRelations[EventTypeName] = []
    
    self.ValidateEdxmlEntityAttributes('eventtype', Attributes)

    self.EventTypes[EventTypeName] = {
      'attributes': Attributes,
      'properties': {},
      'unique-properties': set(),
      'mandatory-properties': set(),
      'singleton-properties': set(),
      'parentmapping': {},
      'relations': {},
      'related-properties': set(),
      'unique': False
      }

    for Class in Attributes['classlist'].split(','):
      if not Class in self.EventTypeClasses:
        self.EventTypeClasses[Class] = set()
      self.EventTypeClasses[Class].add(EventTypeName)
  
  # Internal use only.
  def SetNewEventTypeParent(self, EventTypeName, Attributes):
    self.EventTypes[EventTypeName]['parent'] = Attributes

    try:

      for PropertyMapping in Attributes['propertymap'].split(','):
        ChildProperty, ParentProperty = PropertyMapping.split(':')
        self.EventTypes[EventTypeName]['parentmapping'][ChildProperty] = ParentProperty

    except KeyError, ValueError:

      self.Error("Event type %s contains a parent definition which has an invalid or missing property map." % EventTypeName)
  
  # Internal use only.
  def AddNewProperty(self, EventTypeName, PropertyName, Attributes):
    self.PropertyNames[EventTypeName].append(PropertyName)

    self.ValidateEdxmlEntityAttributes('property', Attributes)
    
    ObjectType = Attributes['object-type']
    self.RequiredObjectTypes.add(ObjectType)
    if not ObjectType in self.ObjectTypeEventTypes:
      self.ObjectTypeEventTypes[ObjectType] = set()
    self.ObjectTypeEventTypes[ObjectType].add(EventTypeName)

    if 'unique' in Attributes and Attributes['unique'].lower() == 'true':
      self.EventTypes[EventTypeName]['unique'] = True
      self.EventTypes[EventTypeName]['unique-properties'].add(PropertyName)

    if 'merge' in Attributes:
      if Attributes['merge'] in ['match', 'min', 'max']:
        self.EventTypes[EventTypeName]['mandatory-properties'].add(PropertyName)
      if Attributes['merge'] in ['match', 'replace', 'min', 'max']:
        self.EventTypes[EventTypeName]['singleton-properties'].add(PropertyName)
      if PropertyName in self.EventTypes[EventTypeName]['parentmapping']:
        self.EventTypes[EventTypeName]['singleton-properties'].add(PropertyName)

    if 'defines-entity' in Attributes and Attributes['defines-entity'].lower() == 'true':
      self.EntityProperties[EventTypeName].add(PropertyName)
      
    self.EventTypes[EventTypeName]['properties'][PropertyName] = {'unique': 'false', 'defines-entity': 'false'}
    self.EventTypes[EventTypeName]['properties'][PropertyName].update(Attributes)

  # Internal use only.
  def AddNewObjectType(self, ObjectTypeName, Attributes):
    
    self.ValidateEdxmlEntityAttributes('objecttype', Attributes)
    self.ValidateDataType(ObjectTypeName, Attributes['data-type'])

    if 'regexp' in Attributes and Attributes['regexp'] != '[\s\S]*':
      try:
        # Note that XML schema regular expressions match the entire object
        # value. We wrap the expression in anchors to mimic this behavior
        self.CompiledObjectTypePatterns[ObjectTypeName] = re.compile('^%s$' % Attributes['regexp'])
      except sre_constants.error as Except:
        self.Error('Definition of object type %s has an invalid regular expresion: "%s"' % (( ObjectTypeName, Attributes['regexp'] )) )

    self.ObjectTypes[ObjectTypeName] = Attributes
    self.ObjectTypeNames.append(ObjectTypeName)

  # Internal use only.
  def AddNewRelation(self, EventTypeName, RelationId, Property1Name, Property2Name, Attributes):
    self.EventTypes[EventTypeName]['related-properties'].add(Property1Name)
    self.EventTypes[EventTypeName]['related-properties'].add(Property2Name)
    self.PropertyRelations[EventTypeName].append(RelationId)

    self.ValidateEdxmlEntityAttributes('relation', Attributes)

    SplitEventType = Attributes['type'].split(':')
    if len(SplitEventType) == 2:
      self.RelationPredicates.add(SplitEventType[1])
    
    self.EventTypes[EventTypeName]['relations'][RelationId] = Attributes

  # Internal use only.
  def AddNewSource(self, SourceUrl, Attributes):
    self.ValidateEdxmlEntityAttributes('source', Attributes)
    self.SourceURLs[SourceUrl] = Attributes

  def CheckPropertyObjectTypes(self):
    """Checks if all object types that properties
    refer to are defined. Calls self.Error when
    a problem is detected."""
    for ObjectTypeName in self.RequiredObjectTypes:
      if not self.ObjectTypeDefined(ObjectTypeName):
        self.Error("Objecttype %s was used in a property definition, but it was not defined." % ObjectTypeName )

  def CheckEventTypePropertyConsistency(self, EventTypeName, PropertyNames):
    """Check if specified list of property names
    is correct for the specified event type.
    Calls self.Error when a problem is detected."""
    for PropertyName in PropertyNames:
      if not self.PropertyDefined(EventTypeName, PropertyName):
        self.Error("Property %s was previously defined as part of eventtype %s, but this definition does not define it." % (( PropertyName, EventTypeName )) )

  def CheckEventTypeRelations(self, EventTypeName):
    """Check if the relation definitions for
    specified eventtype are correct.
    Calls self.Error when a problem is detected."""
    
    for RelationId in self.EventTypes[EventTypeName]['relations']:
      PropertyA   = None
      PropertyB   = None
      Description = None
      
      for Attribute in self.EventTypes[EventTypeName]['relations'][RelationId]:
        if Attribute == 'property1':
          PropertyA = self.EventTypes[EventTypeName]['relations'][RelationId][Attribute]
        elif Attribute == 'property2':
          PropertyB = self.EventTypes[EventTypeName]['relations'][RelationId][Attribute]
        elif Attribute == 'description':
          Description = self.EventTypes[EventTypeName]['relations'][RelationId][Attribute]
      
      Placeholders = re.findall(self.PlaceHolderPattern, Description)
      
      if not PropertyA in Placeholders:
        self.Error("Event type %s defines relation %s which does not have one of its properties (%s) in the description." % (( EventTypeName, RelationId, PropertyA )) )
    
      if not PropertyB in Placeholders:
        self.Error("Event type %s defines relation %s which does not have one of its properties (%s) in the description." % (( EventTypeName, RelationId, PropertyB )) )
        
      if not self.PropertyDefined(EventTypeName, PropertyA):
        self.Error("Event type %s defines relation %s which refers to property %s, which does not exist in this event type." % (( EventTypeName, RelationId, PropertyA )))
        
      if not self.PropertyDefined(EventTypeName, PropertyB):
        self.Error("Event type %s defines relation %s which refers to property %s, which does not exist in this event type." % (( EventTypeName, RelationId, PropertyB )))

  def CheckEventTypeParents(self, EventTypeName):
    """Checks if parent definition of given event type
    is valid, if there is any parent definition.
    
    Parameters:
    
    EventTypeName -- Name of event type
    
    """
    
    if not 'parent' in self.EventTypes[EventTypeName]: return

    ParentAttribs = self.EventTypes[EventTypeName]['parent']

    if not ParentAttribs['eventtype'] in self.EventTypes:
      self.Error("Event type %s contains a parent definition which refers to event type %s which is not defined." % (( EventTypeName, ParentAttribs['eventtype'] )))

    for UniqueParentProperty in self.EventTypes[ParentAttribs['eventtype']]['unique-properties']:
      if not UniqueParentProperty in self.EventTypes[EventTypeName]['parentmapping'].values():
        self.Error("Event type %s contains a parent definition which lacks a mapping for unique parent property '%s'." % (( EventTypeName, UniqueParentProperty )) )
      
    for ChildProperty, ParentProperty in self.EventTypes[EventTypeName]['parentmapping'].items():
      ChildMergeStrategy = self.EventTypes[EventTypeName]['properties'][ChildProperty]['merge']

      if not ChildProperty in self.EventTypes[EventTypeName]['properties']:
        self.Error("Event type %s contains a parent definition which refers to unknown child property '%s'." % (( EventTypeName, ChildProperty )) )

      if ChildMergeStrategy != 'match' and ChildMergeStrategy != 'drop':
        self.Error("Event type %s contains a parent definition which refers to child property '%s'. This property has merge strategy %s, which is not allowed for properties that are used in parent definitions." % (( EventTypeName, ChildProperty, ChildMergeStrategy )) )

      if not ParentProperty in self.EventTypes[ParentAttribs['eventtype']]['unique-properties']:
        self.Error("Event type %s contains a parent definition which refers to parent property '%s', but this property is not unique, or is does not exist." % (( EventTypeName, ParentProperty )) )


  def CheckReporterString(self, EventTypeName, String, PropertyNames, CheckCompleteness = False):
    """Checks if given event type reporter string makes sense. Optionally,
    it can also check if all given properties are present in the string.

    Parameters:

    EventTypeName     -- Name of event type
    String            -- The reporter string
    PropertyNames     -- List of property names of event type
    CheckCompleteness -- Check if all properties are present in string. (optional, defaults to False)

    """

    # Test if reporter string grammar is correct, by
    # checking that curly brackets are balanced.
    CurlyNestings = {'{': 1, '}': -1}
    Nesting = 0
    for Curly in [Char for Char in String if Char in ['{', '}']]:
      Nesting += CurlyNestings[Curly]
      if Nesting < 0:
        self.Error('The following reporter string contains unbalanced curly brackets:\n%s\n' % String)
        Nesting = 0
        break
    if Nesting != 0:
      self.Error('The following reporter string contains unbalanced curly brackets:\n%s\n' % String)

    PlaceholderStrings = re.findall(self.ReporterPlaceholderPattern, String)
    ReferredProperties = []

    for String in PlaceholderStrings:
      StringComponents = String.split(':')
      if len(StringComponents) == 1:
        # Placeholder does not contain a formatter.
        if StringComponents[0] in PropertyNames:
          ReferredProperties.append(StringComponents[0])
          continue
      else:
        # Some kind of string formatter was used.
        # Figure out which one, and check if it
        # is used correctly.
        if StringComponents[0] in ['DURATION', 'TIMESPAN']:
          DurationProperties = StringComponents[1].split(',')
          if len(DurationProperties) != 2:
            self.Error("Event type %s contains a reporter string containing a string formatter (%s) which requires two properties, but %d properties were specified." % (( EventTypeName, StringComponents[0], len(DurationProperties) )) )
          if DurationProperties[0] in PropertyNames and DurationProperties[1] in PropertyNames:
            ReferredProperties.append(DurationProperties[0])
            ReferredProperties.append(DurationProperties[1])

            # Check that both properties are timestamps
            if self.GetObjectTypeDataType(self.GetPropertyObjectType(EventTypeName, DurationProperties[0])) != 'timestamp':
              self.Error("Event type %s contains a reporter string which uses a time related formatter, but the used property (%s) is not a timestamp." % (( EventTypeName, DurationProperties[0] )) )
            if self.GetObjectTypeDataType(self.GetPropertyObjectType(EventTypeName, DurationProperties[1])) != 'timestamp':
              self.Error("Event type %s contains a reporter string which uses a time related formatter, but the used property (%s) is not a timestamp." % (( EventTypeName, DurationProperties[1] )) )

            continue
        else:
          if not StringComponents[0] in self.KnownFormatters:
            self.Error("Event type %s contains a reporter string which refers to an unknown formatter: %s" % (( EventTypeName, StringComponents[0] )) )

          if StringComponents[0] in ['DATE', 'DATETIME', 'FULLDATETIME', 'WEEK', 'MONTH', 'YEAR']:
            # Check that only one property is specified after the formatter
            if len(StringComponents[1].split(',')) > 1:
              self.Error("Event type %s contains a reporter string which uses the %s formatter, which accepts just one property. Multiple properties were specified: %s" % (( EventTypeName, StringComponents[0], StringComponents[1] )) )
            # Check that property is a timestamp
            if self.GetObjectTypeDataType(self.GetPropertyObjectType(EventTypeName, StringComponents[1])) != 'timestamp':
              self.Error("Event type %s contains a reporter string which uses the %s formatter. The used property (%s) is not a timestamp, though." % (( EventTypeName, StringComponents[0], StringComponents[1] )) )

          elif StringComponents[0] in ['LATITUDE', 'LONGITUDE', 'BYTECOUNT', 'COUNTRYCODE', 'FILESERVER', 'BOOLEAN_ON_OFF', 'BOOLEAN_IS_ISNOT']:
            # Check that no additional options are present
            if len(StringComponents) > 2:
              self.Error("Event type %s contains a reporter string which uses the %s formatter. This formatter accepts no options, but they were specified: %s" % (( EventTypeName, StringComponents[0], String )) )
            # Check that only one property is specified after the formatter
            if len(StringComponents[1].split(',')) > 1:
              self.Error("Event type %s contains a reporter string which uses the %s formatter. This formatter accepts just one property. Multiple properties were given though: %s" % (( EventTypeName, StringComponents[0], StringComponents[1] )) )
            if StringComponents[0] in ['BOOLEAN_ON_OFF', 'BOOLEAN_IS_ISNOT']:
              # Check that property is a boolean
              if self.GetObjectTypeDataType(self.GetPropertyObjectType(EventTypeName, StringComponents[1])) != 'boolean':
                self.Error("Event type %s contains a reporter string which uses the %s formatter. The used property (%s) is not a boolean, though." % (( EventTypeName, StringComponents[0], StringComponents[1] )) )

          elif StringComponents[0] == 'CURRENCY':
            if len(StringComponents) != 3:
              self.Error("Event type %s contains a reporter string which uses a malformed %s formatter: %s" % (( EventTypeName, StringComponents[0], String )) )

          elif StringComponents[0] == 'EMPTY':
            if len(StringComponents) != 3:
              self.Error("Event type %s contains a reporter string which uses a malformed %s formatter: %s" % (( EventTypeName, StringComponents[0], String )) )

          elif StringComponents[0] == 'BOOLEAN_STRINGCHOICE':
            if len(StringComponents) != 4:
              self.Error("Event type %s contains a reporter string which uses a malformed %s formatter: %s" % (( EventTypeName, StringComponents[0], String )) )
            # Check that property is a boolean
            if self.GetObjectTypeDataType(self.GetPropertyObjectType(EventTypeName, StringComponents[1])) != 'boolean':
              self.Error("Event type %s contains a reporter string which uses the %s formatter. The used property (%s) is not a boolean, though." % (( EventTypeName, StringComponents[0], StringComponents[1] )) )

          else:
              self.Error("Event type %s contains a reporter string which uses an unknown formatter: %s" % (( EventTypeName, StringComponents[0] )) )

          if StringComponents[1] in PropertyNames:
            ReferredProperties.append(StringComponents[1])
            continue

      self.Error("Event type %s contains a reporter string which refers to one or more nonexisting properties: %s" % (( EventTypeName, String )) )

    if CheckCompleteness:
      for PropertyName in PropertyNames:
          if not PropertyName in ReferredProperties:
            self.Warning("Event type %s contains an incomplete long reporter string. The property '%s' is missing." % (( EventTypeName, PropertyName )))

  # Checks if two sets of attributes of EDXML entities (eventtype, property, relation, ...)
  # are mutually consistent. The parameters CurrentAttributes and UpdatedAttributes
  # should contain dictionaries with attributes of the entity.
  #
  # Internal use only.
  def CheckEdxmlEntityConsistency(self, Entity, EntityDescription, CurrentAttributes, UpdatedAttributes):
    
    Current = set(CurrentAttributes.keys())
    Update  = set(UpdatedAttributes.keys())
    
    AttribsAdded    = Update - Current
    AttribsRetained = Update & Current
    AttribsRemoved  = Current - Update
    
    # First we check if the attributes that are retained in the
    # update are consistent with the exiting atribute values.
    
    for Attribute in AttribsRetained:
      if CurrentAttributes[Attribute] != UpdatedAttributes[Attribute]:
        self.Error("Attribute %s of %s '%s' does not match previous definition:\nNew:      %s\nExisting: %s\n" % (( Attribute, Entity, EntityDescription, UpdatedAttributes[Attribute], CurrentAttributes[Attribute] )))
        
    # At the moment, we do not accept new attributes to appear or 
    # existing attributes to disappear, unless they are optional
    # and have a default value. These optional attributes with
    # or without defaults cause some exceptions to the above rule.
    # We will get rid of most of these exceptions as soon as EDXML
    # version 3 hits the road.
    
    for Attrib in AttribsAdded:
      if self.EDXMLEntityAttributes[Entity][Attrib]['mandatory']:
        self.Error("Definition of %s '%s' contains mandatory attribute that was not previously defined: %s" % (( Entity, EntityDescription, Attrib)) )
      else:
        if 'default' in self.EDXMLEntityAttributes[Entity][Attrib]:
          if UpdatedAttributes[Attrib] != self.EDXMLEntityAttributes[Entity][Attrib]['default']:
            self.Error("Definition of %s '%s' contains attribute with non-default value (%s) that was not previously defined: %s" % (( Entity, EntityDescription, UpdatedAttributes[Attrib], Attrib)) )
        else:
          self.Error("Definition of %s '%s' contains attribute that was not previously defined and has no default value: %s" % (( Entity, EntityDescription, Attrib)) )
    
    for Attrib in AttribsRemoved:
      if self.EDXMLEntityAttributes[Entity][Attrib]['mandatory']:
        self.Error("Definition of %s '%s' lacks mandatory attribute: %s" % (( Entity, EntityDescription, Attrib)) )
      else:
        if 'default' in self.EDXMLEntityAttributes[Entity][Attrib]:
          if CurrentAttributes[Attrib] != self.EDXMLEntityAttributes[Entity][Attrib]['default']:
            self.Error("Previous definition of %s '%s' contains optional attribute %s with non-default value (%s) while new definition does not define it." % (( Entity, EntityDescription, Attrib, CurrentAttributes[Attrib] )) )
        else:
          self.Error("Definition of %s '%s' lacks optional attribute that was previously defined and has no default value: %s" % (( Entity, EntityDescription, Attrib)) )
  
  # Checks the attributes of a specific EDXML entity (eventtype, 
  # objecttype, relation, ...) against the constaints as specified in
  # self.EDXMLEntityAttributes.
  # 
  # Internal use only.
  def ValidateEdxmlEntityAttributes(self, EntityName, Attributes):

    for Attribute in self.EDXMLEntityAttributes[EntityName]:
      
      if Attribute in Attributes:
        Value = Attributes[Attribute]
      else:
        if self.EDXMLEntityAttributes[EntityName][Attribute]['mandatory']:
          self.Error("Definition of %s lacks mandatory attribute '%s'." % (( EntityName, Attribute )) )
        else:
          Value = None
    
      if Value:
    
        if self.EDXMLEntityAttributes[EntityName][Attribute]['length']:
          if len(Value) > self.EDXMLEntityAttributes[EntityName][Attribute]['length']:
            self.Error("Value of %s attribute %s is too long: %s " % (( EntityName, Attribute, Value )))
        if self.EDXMLEntityAttributes[EntityName][Attribute]['pattern']:
          if not re.match(self.EDXMLEntityAttributes[EntityName][Attribute]['pattern'], Value):
            self.Error("Value of %s attribute %s is invalid: %s " % (( EntityName, Attribute, Value )))
    
    UnknownAttributes = list(set(Attributes.keys()) - set(self.EDXMLEntityAttributes[EntityName].keys()))

    if len(UnknownAttributes) > 0:
      self.Error("Definition of %s contains unknown attributes: %s" % (( EntityName, ','.join(UnknownAttributes) )) )
    
  def UniqueSourceIDs(self):
    """Source IDs are required to be unique only
    within a single EDXML file. When multiple 
    EDXML files are parsed using the same EDXMLParser
    instance, it may happen that different sources have
    the same ID. This function changes the Source IDs
    of all known sources to be unique.
    
    It returns a mapping that maps old Source ID into
    new Source ID."""
  
    Counter = 1
    Mapping = {}
    for SourceUrl in self.SourceURLs:
      Mapping[SourceUrl] = str(Counter)
      self.SourceURLs[SourceUrl]['source-id'] = str(Counter)
      self.SourceIDs[str(Counter)] = SourceUrl
      Counter += 1
    return Mapping

  def MergeEvents(self, EventTypeName, EventObjectsA, EventObjectsB):
    """Merges the objects of an event 'B' with the objects
    of another event 'A'. The arguments EventObjectsA
    and EventObjectsB should be dictionaries where the keys are
    property names and the values lists of object values.
    
    The objects in EventObjectsA are updated using the
    objects from EventObjectsB. It returns True when EventObjectsA
    was modified, False otherwise.
    
    Parameters:
    
    EventTypeName -- Name of event type of the events
    EventObjectsA -- Objects of event A
    EventObjectsB -- Objects of event B
    
    """
    
    if self.EventTypes[EventTypeName]['unique'] == False:
      self.Error("MergeEvent was called for event type %s, which is not a unique event type." % EventTypeName)
    
    Original = {}
    Source = {}
    Target = {}
    
    for PropertyName in self.GetEventTypeProperties(EventTypeName):
      if PropertyName in EventObjectsA: 
        Original[PropertyName] = set(EventObjectsA[PropertyName])
        Target[PropertyName] = set(EventObjectsA[PropertyName])
      else:
        Original[PropertyName] = set()
        Target[PropertyName] = set()
      if PropertyName in EventObjectsB: Source[PropertyName] = set(EventObjectsB[PropertyName])
      else: Source[PropertyName] = set()
    
    # Now we update the objects in Target
    # using the values in Source
    for PropertyName in Source:

      if not PropertyName in self.EventTypes[EventTypeName]['unique-properties']:
        # Not a unique property, needs to be merged.
        MergeStrategy = self.EventTypes[EventTypeName]['properties'][PropertyName]['merge']
        
        if MergeStrategy in ['min', 'max']:
          SplitDataType = self.GetObjectTypeDataType(self.GetPropertyObjectType(EventTypeName, PropertyName)).split(':')
          if SplitDataType[0] in ['number', 'timestamp']:
            
            Values = set()
            
            if SplitDataType[0] == 'timestamp':
              
              Values = Source[PropertyName] | Target[PropertyName]

            else:  
              
              if SplitDataType[1] in ['float', 'double']:
                for Value in Source[PropertyName]: Values.add(float(Value))
                for Value in Target[PropertyName]: Values.add(float(Value))
              elif SplitDataType[1] == 'decimal':
                for Value in Source[PropertyName]: Values.add(Decimal(Value))
                for Value in Target[PropertyName]: Values.add(Decimal(Value))
              else:
                for Value in Source[PropertyName]: Values.add(int(Value))
                for Value in Target[PropertyName]: Values.add(int(Value))
              
            if MergeStrategy == 'min':
              Target[PropertyName] = set([str(min(Values))])
            else:
              Target[PropertyName] = set([str(max(Values))])
          
        elif MergeStrategy == 'add':
          Target[PropertyName] = Source[PropertyName] | Target[PropertyName]

        elif MergeStrategy == 'replace':
          Target[PropertyName] = Source[PropertyName]

    # Remove any objects due to replace strategy
    for PropertyName in [Property for Property in self.GetEventTypeProperties(EventTypeName) if Property not in Source and Property in Target]:
      if self.EventTypes[EventTypeName]['properties'][PropertyName]['merge'] == 'replace':
        Target[PropertyName] = set()

    # Determine if anything changed

    EventUpdated = False
    for PropertyName in self.GetEventTypeProperties(EventTypeName):
      if not PropertyName in Original and len(Target[PropertyName]) > 0:
        EventUpdated = True
        break
      if Target[PropertyName] != Original[PropertyName]:
        EventUpdated = True
        break
    
    # Modify EventObjectsA if needed
    
    if EventUpdated:
      EventObjectsA.clear()
      for PropertyName in Target:
        EventObjectsA[PropertyName] = []
        for Value in Target[PropertyName]:
          EventObjectsA[PropertyName].append(Value)
      return True
    else:
      return False

  def ComputeStickyHash(self, EventTypeName, EventObjects, EventContent):
    """Computes a sticky hash from given event. The EventObjects argument
    should be a list containing dictionaries representing the objects. The
    dictionaries should contain the property name stored under the 'property'
    key and the value stored under the 'value' key.

    Note that the supplied object values must be normalized using the
    NormalizeObject method of the EDXMLBase class.

    Returns a hexadecimal string representation of the hash.

    """

    ObjectStrings = set()

    for EventObject in EventObjects:
      Property = unicode(EventObject['property'])
      Value    = EventObject['value']
      if self.EventTypeIsUnique(EventTypeName) and self.PropertyIsUnique(EventTypeName, Property) == False:
        # We use only unique properties for
        # hash computation. Skip this one.
        continue
      ObjectType = self.GetPropertyObjectType(EventTypeName, Property)
      DataType = self.GetObjectTypeDataType(ObjectType).split(':')

      if DataType[0] == 'number' and DataType[1] in ['float', 'double']:
        # Floating point objects are ignored.
        continue

      # Normalize the object value to a unicode string
      try:
        NormalizedValue = self.NormalizeObject(Value, DataType)
      except EDXMLError as Except:
        self.Error("Invalid value in property %s of event type %s: '%s': %s" % (( Property, EventTypeName, Value, Except )))

      ObjectStrings.add(Property + u':' + NormalizedValue)

    # Now we compute the SHA1 hash value of the unicode
    # string representation of the event, and output in hex

    if self.EventTypeIsUnique(EventTypeName):
      return hashlib.sha1((EventTypeName + '\n' + '\n'.join(sorted(ObjectStrings))).encode('utf-8')).hexdigest()
    else:
      return hashlib.sha1((EventTypeName + '\n' + '\n'.join(sorted(ObjectStrings)) + '\n' + EventContent).encode('utf-8')).hexdigest()

  def ComputeStickyHashV3(self, EventTypeName, SourceUrl, EventObjects, EventContent):
    """Computes a sticky hash from given event, using the hashing algorithm
    from EDXML specification version 3.x. The EventObjects argument
    should be a list containing dictionaries representing the objects. The
    dictionaries should contain the property name stored under the 'property'
    key and the value stored under the 'value' key.

    Note that the supplied object values must be normalized using the
    NormalizeObject method of the EDXMLBase class.

    Returns a hexadecimal string representation of the hash.

    """

    ObjectStrings = set()

    for EventObject in EventObjects:
      Property = unicode(EventObject['property'])
      Value    = EventObject['value']
      if self.EventTypeIsUnique(EventTypeName) and self.PropertyIsUnique(EventTypeName, Property) == False:
        # We use only unique properties for
        # hash computation. Skip this one.
        continue
      ObjectType = self.GetPropertyObjectType(EventTypeName, Property)
      DataType = self.GetObjectTypeDataType(ObjectType).split(':')

      if DataType[0] == 'number' and DataType[1] in ['float', 'double']:
        # Floating point objects are ignored.
        continue

      # Normalize the object value to a unicode string
      try:
        NormalizedValue = self.NormalizeObject(Value, DataType)
      except EDXMLError as Except:
        self.Error("Invalid value in property %s of event type %s: '%s': %s" % (( Property, EventTypeName, Value, Except )))

      ObjectStrings.add(Property + u':' + NormalizedValue)

    # Now we compute the SHA1 hash value of the unicode
    # string representation of the event, and output in hex

    if self.EventTypeIsUnique(EventTypeName):
      return hashlib.sha1((SourceUrl + '\n' + EventTypeName + '\n' + '\n'.join(sorted(ObjectStrings))).encode('utf-8')).hexdigest()
    else:
      return hashlib.sha1((SourceUrl + '\n' + EventTypeName + '\n' + '\n'.join(sorted(ObjectStrings)) + '\n' + EventContent).encode('utf-8')).hexdigest()

  def GenerateEventTypeXML(self, EventTypeName, XMLGenerator, Indent = 0):
    """Generates an EDXML fragment which defines specified
    eventtype. Can be useful for constructing new EDXML
    files based on existing event type definitions.
    
    Arguments:
    
    EventTypeName -- Name of the event type
    XMLGenerator  -- Sax XMLGenerator instance
    Indent        -- Number of spaces of indentation in output lines (optional, defaults to zero)
    
    """
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('eventtype', AttributesImpl(self.GetEventTypeAttributes(EventTypeName)))
    Indent += 2
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('properties', AttributesImpl({}))
    Indent += 2
    
    for PropertyName in self.GetEventTypeProperties(EventTypeName):
    
      XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
      XMLGenerator.startElement('property', AttributesImpl(self.GetPropertyAttributes(EventTypeName, PropertyName)))
      XMLGenerator.endElement('property')
  
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.endElement('properties')
    Indent -= 2
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('relations', AttributesImpl({}))
    Indent += 2

    for RelationId in self.GetEventTypePropertyRelations(EventTypeName):
      
      XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
      XMLGenerator.startElement('relation', AttributesImpl(self.GetPropertyRelationAttributes(EventTypeName, RelationId)))
      XMLGenerator.endElement('relation')
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.endElement('relations')
    Indent -= 2
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.endElement('eventtype')
    Indent -= 2

  def GenerateObjectTypeXML(self, ObjectTypeName, XMLGenerator, Indent = 0):
    """Generates an EDXML fragment which defines specified
    object type. Can be useful for constructing new EDXML
    files based on existing object type definitions.
    
    Arguments:
    
    EventTypeName -- Name of the event type
    XMLGenerator  -- Sax XMLGenerator instance
    Indent        -- Number of spaces of indentation in output lines (optional, defaults to zero)
    
    """
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('objecttype', AttributesImpl(self.GetObjectTypeAttributes(ObjectTypeName)))
    XMLGenerator.endElement('objecttype')
    
  def GenerateEventSourceXML(self, SourceUrl, XMLGenerator, Indent = 0):
    """Generates an EDXML fragment which defines specified
    event source. Can be useful for constructing new EDXML
    files based on existing event source definitions.
    
    EventTypeName -- Name of the event type
    XMLGenerator  -- Sax XMLGenerator instance
    Indent        -- Number of spaces of indentation in output lines (optional, defaults to zero)

    """
  
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('source', AttributesImpl(self.GetSourceURLProperties(SourceUrl)))
    XMLGenerator.endElement('source')
      
  def GenerateXMLDefinitions(self, XMLGenerator, IncludeSources = True):
    """Generates a full EDXML <definitions> section, containing
    all known event types, event types and optionally sources.
    
    Parameters:
    
    XMLGenerator   -- Sax XMLGenerator instance
    IncludeSources -- Optional boolean, include source definitions yes or no (default is True)
    
    """
    
    Indent = 2
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('definitions', AttributesImpl({}))
    Indent += 2
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('eventtypes', AttributesImpl({}))
    Indent += 2
    
    for EventTypeName in self.GetEventTypeNames():
      self.GenerateEventTypeXML(EventTypeName, XMLGenerator, Indent)
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.endElement('eventtypes')
    Indent -= 2
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('objecttypes', AttributesImpl({}))
    Indent += 2
    
    for ObjectTypeName in self.GetObjectTypeNames():
      self.GenerateObjectTypeXML(ObjectTypeName, XMLGenerator, Indent)
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.endElement('objecttypes')
    Indent -= 2
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.startElement('sources', AttributesImpl({}))
    Indent += 2

    if IncludeSources:
      for SourceUrl in self.GetSourceURLs():
        self.GenerateEventSourceXML(SourceUrl, XMLGenerator, Indent)
    
    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.endElement('sources')
    Indent -= 2

    XMLGenerator.ignorableWhitespace('\n'.ljust(Indent))
    XMLGenerator.endElement('definitions')
    Indent -= 2

  def OpenXSD(self):
    """Start generating an XSD schema from stored
    definitions. Always call this before constructing
    a (partial) XSD schema."""
    self.SchemaXSD = etree.Element('{%s}schema' % self.XSD['xs'], nsmap=self.XSD)
    self.CurrentElementXSD = self.SchemaXSD

  def CloseXSD(self):
    """Finalize generated XSD and return it as a string."""
    return etree.tostring(self.SchemaXSD, pretty_print = True, encoding='utf-8')
    
  # Internal convenience function
  def OpenElementXSD(self, ElementName):
    self.CurrentElementXSD = etree.SubElement(self.CurrentElementXSD, "{%s}%s" % (( self.XSD['xs'], ElementName )) )
    return self.CurrentElementXSD
  
  # Internal convenience function
  def CloseElementXSD(self):
    self.CurrentElementXSD = self.CurrentElementXSD.getparent()
    
  def GenerateEventTypeXSD(self, EventTypeName):
    """Generates an XSD fragment related to the event type
    definition of specified event type. Can be useful for
    generating modular XSD schemas or constructing full
    EDXML validation schemas.
    
    Make sure to call OpenXSD() first.
    
    """
    
    self.OpenElementXSD('element').set('name', 'eventtype')
    self.OpenElementXSD('complexType')
    
    self.OpenElementXSD('sequence')
    self.OpenElementXSD('element').set('name', 'properties')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence')
    for EventPropertyName in self.GetEventTypeProperties(EventTypeName):
      self.OpenElementXSD('element').set('name', 'property')
      self.OpenElementXSD('complexType')
      for Attribute, Value in self.GetPropertyAttributes(EventTypeName, EventPropertyName).items():
        self.OpenElementXSD('attribute').set('name', 'name')
        self.CurrentElementXSD.set('name', Attribute)
        self.CurrentElementXSD.set('type', 'xs:string')
        self.CurrentElementXSD.set('fixed', Value)
        self.CloseElementXSD()
      self.CloseElementXSD()
      self.CloseElementXSD()
    self.CloseElementXSD()
      
    self.CloseElementXSD()
    self.CloseElementXSD()

    self.OpenElementXSD('element').set('name', 'relations')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence')

    for RelationId in self.GetEventTypePropertyRelations(EventTypeName):
      self.OpenElementXSD('element').set('name', 'relation')
      self.OpenElementXSD('complexType')
      for Attribute, Value in self.GetPropertyRelationAttributes(EventTypeName, RelationId).items():
        self.OpenElementXSD('attribute').set('name', 'name')
        self.CurrentElementXSD.set('name', Attribute)
        self.CurrentElementXSD.set('type', 'xs:string')
        self.CurrentElementXSD.set('fixed', Value)
        self.CloseElementXSD()
      self.CloseElementXSD()
      self.CloseElementXSD()
    
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()
    
    for Attribute, Value in self.GetEventTypeAttributes(EventTypeName).items():
      self.OpenElementXSD('attribute').set('name', 'name')
      self.CurrentElementXSD.set('name', Attribute)
      self.CurrentElementXSD.set('type', 'xs:string')
      self.CurrentElementXSD.set('fixed', Value)
      self.CloseElementXSD()
    
    self.CloseElementXSD()
    self.CloseElementXSD()

  def GenerateObjectTypeXSD(self, ObjectTypeName):    
    """Generates an XSD fragment related to the object type
    definition of specified object type. Can be useful for
    generating modular XSD schemas or constructing full
    EDXML validation schemas.
    
    Make sure to call OpenXSD() first.

    """
    
    self.OpenElementXSD('element').set('name', 'objecttype')
    self.OpenElementXSD('complexType')
    for Attribute, Value in self.GetObjectTypeAttributes(ObjectTypeName).items():
      self.OpenElementXSD('attribute').set('name', 'name')
      self.CurrentElementXSD.set('name', Attribute)
      self.CurrentElementXSD.set('type', 'xs:string')
      self.CurrentElementXSD.set('fixed', Value)
      self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()

  def GenerateFullXSD(self):
    """Generates an full XSD schema for EDXML files that
    contain all known definitions of event types, object
    types and sources.

    Make sure to call OpenXSD() first.

    """
  
    self.OpenElementXSD('element').set('name', 'events')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence')
    self.OpenElementXSD('element').set('name', 'definitions')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence')
    self.OpenElementXSD('element').set('name', 'eventtypes')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence')

    for EventTypeName in self.GetEventTypeNames():
      self.GenerateEventTypeXSD(EventTypeName)
     
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()
    
    self.OpenElementXSD('element').set('name', 'objecttypes')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence')

    for ObjectTypeName in self.GetObjectTypeNames():
      print ObjectTypeName
      self.GenerateObjectTypeXSD(ObjectTypeName)
    
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()
    
    self.OpenElementXSD('element').set('name', 'sources')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence')

    for SourceId in self.GetSourceIDs():
      self.OpenElementXSD('element').set('name', 'source')
      self.OpenElementXSD('complexType')
      for Attribute, Value in self.GetSourceIdProperties(SourceId).items():
        self.OpenElementXSD('attribute').set('name', 'name')
        self.CurrentElementXSD.set('name', Attribute)
        self.CurrentElementXSD.set('type', 'xs:string')
        self.CurrentElementXSD.set('fixed', Value)
        self.CloseElementXSD()
      self.CloseElementXSD()
      self.CloseElementXSD()
    
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()
    
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()

    self.OpenElementXSD('element').set('name', 'eventgroups')
    self.OpenElementXSD('complexType')
    self.OpenElementXSD('sequence').set('minOccurs', '0')
    self.CurrentElementXSD.set('maxOccurs', 'unbounded')

    self.OpenElementXSD('element').set('name', 'eventgroup')
    self.OpenElementXSD('complexType')
    
    self.OpenElementXSD('sequence').set('minOccurs', '0')
    self.CurrentElementXSD.set('maxOccurs', 'unbounded')
    self.OpenElementXSD('element').set('name', 'event')
    
    self.CloseElementXSD()
    self.CloseElementXSD()
    
    self.OpenElementXSD('attribute')
    self.CurrentElementXSD.set('name', 'source-id')
    self.CurrentElementXSD.set('type', 'xs:string')
    self.CloseElementXSD()
    self.OpenElementXSD('attribute')
    self.CurrentElementXSD.set('name', 'event-type')
    self.CurrentElementXSD.set('type', 'xs:string')
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()
    
    self.CloseElementXSD()
    self.CloseElementXSD()
    self.CloseElementXSD()
    
    self.CloseElementXSD()
    self.CloseElementXSD()
  
  def OpenRelaxNG(self):
    """Start generating a RelaxNG schema from stored
    definitions. Always call this before constructing
    a (partial) RelaxNG schema."""
    self.SchemaRelaxNG = None

  def CloseRelaxNG(self):
    """Finalize RelaxNG schema and return it as a string."""
    Schema = etree.tostring(self.SchemaRelaxNG, pretty_print = True, encoding='utf-8')
    self.SchemaRelaxNG = None
    return Schema
    
  # Internal convenience function
  def OpenElementRelaxNG(self, ElementName):
    self.CurrentElementRelaxNG = etree.SubElement(self.CurrentElementRelaxNG, ElementName )
    return self.CurrentElementRelaxNG
  
  # Internal convenience function
  def CloseElementRelaxNG(self):
    self.CurrentElementRelaxNG = self.CurrentElementRelaxNG.getparent()
    
  def GenerateEventTypeRelaxNG(self, EventTypeName):
    """Generates a RelaxNG fragment related to the event type
    definition of specified event type. Can be useful for
    generating modular RelaxNG schemas or constructing full
    EDXML validation schemas.
    
    Make sure to call OpenRelaxNG() first.
    
    """

    if self.SchemaRelaxNG == None:
      # Apparently, we are generating an eventtyoe
      # definition that is not part of a bigger schema.
      self.CurrentElementRelaxNG = etree.Element('grammar')
      self.CurrentElementRelaxNG.set('xmlns', 'http://relaxng.org/ns/structure/1.0')
      self.SchemaRelaxNG = self.CurrentElementRelaxNG
    else:
      self.OpenElementRelaxNG('grammar')
    
    self.OpenElementRelaxNG('start')
    self.OpenElementRelaxNG('ref').set('name', 'eventtypedef')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.OpenElementRelaxNG('define').set('name', 'eventtypedef')
    
    self.OpenElementRelaxNG('element').set('name', 'eventtype')
    for Attribute, Value in self.GetEventTypeAttributes(EventTypeName).items():
      self.OpenElementRelaxNG('attribute').set('name', Attribute)
      self.OpenElementRelaxNG('value').set('type', 'string')
      self.CurrentElementRelaxNG.text = Value
      self.CloseElementRelaxNG()
      self.CloseElementRelaxNG()
      
    self.OpenElementRelaxNG('element').set('name', 'properties')
    self.OpenElementRelaxNG('oneOrMore')
    self.OpenElementRelaxNG('choice')
    for EventPropertyName in self.GetEventTypeProperties(EventTypeName):
      self.OpenElementRelaxNG('element').set('name', 'property')
      for Attribute, Value in self.GetPropertyAttributes(EventTypeName, EventPropertyName).items():
        self.OpenElementRelaxNG('attribute').set('name', Attribute)
        self.OpenElementRelaxNG('value').set('type', 'string')
        self.CurrentElementRelaxNG.text = Value
        self.CloseElementRelaxNG()
        self.CloseElementRelaxNG()
      self.CloseElementRelaxNG()
      
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()

    Relations = self.GetEventTypePropertyRelations(EventTypeName)
    
    self.OpenElementRelaxNG('element').set('name', 'relations')
    
    if len(Relations) > 0:
    
      for RelationId in self.GetEventTypePropertyRelations(EventTypeName):
        self.OpenElementRelaxNG('element').set('name', 'relation')
        for Attribute, Value in self.GetPropertyRelationAttributes(EventTypeName, RelationId).items():
          self.OpenElementRelaxNG('attribute').set('name', Attribute)
          self.OpenElementRelaxNG('value').set('type', 'string')
          self.CurrentElementRelaxNG.text = Value
          self.CloseElementRelaxNG()
          self.CloseElementRelaxNG()
        self.CloseElementRelaxNG()
      
    else:
      
      self.OpenElementRelaxNG('empty')
      self.CloseElementRelaxNG()
      
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()

    return    


  def GenerateObjectTypeRelaxNG(self, ObjectTypeName):    
    """Generates a RelaxNG fragment related to the object type
    definition of specified object type. Can be useful for
    generating modular RelaxNG schemas or constructing full
    EDXML validation schemas.
    
    Make sure to call OpenRelaxNG() first.
    
    """
    
    if self.SchemaRelaxNG == None:
      # Apparently, we are generating an objecttype
      # definition that is not part of a bigger schema.
      self.CurrentElementRelaxNG = etree.Element('grammar')
      self.CurrentElementRelaxNG.set('xmlns', 'http://relaxng.org/ns/structure/1.0')
      self.SchemaRelaxNG = self.CurrentElementRelaxNG
    else:
      self.OpenElementRelaxNG('grammar')

    self.OpenElementRelaxNG('start')
    self.OpenElementRelaxNG('ref').set('name', 'objecttypedef')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.OpenElementRelaxNG('define').set('name', 'objecttypedef')
      
    self.OpenElementRelaxNG('element').set('name', 'objecttype')
    for Attribute, Value in self.GetObjectTypeAttributes(ObjectTypeName).items():
      self.OpenElementRelaxNG('attribute').set('name', Attribute)
      self.OpenElementRelaxNG('value').set('type', 'string')
      self.CurrentElementRelaxNG.text = Value
      self.CloseElementRelaxNG()
      self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    return
  

  def GenerateEventRelaxNG(self, EventTypeName):
    """Generates a RelaxNG fragment related to the object type
    definition of specified object type. Can be useful for
    generating modular RelaxNG schemas or constructing full
    EDXML validation schemas.
    
    Make sure to call OpenRelaxNG() first.
    
    """
    
    if self.SchemaRelaxNG == None:
      # Apparently, we are generating an objecttype
      # definition that is not part of a bigger schema.
      self.CurrentElementRelaxNG = etree.Element('grammar')
      self.CurrentElementRelaxNG.set('xmlns', 'http://relaxng.org/ns/structure/1.0')
      self.SchemaRelaxNG = self.CurrentElementRelaxNG
    else:
      self.OpenElementRelaxNG('grammar')

    self.OpenElementRelaxNG('start')
    self.OpenElementRelaxNG('ref').set('name', 'eventdef-' + EventTypeName)
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.OpenElementRelaxNG('define').set('name', 'eventdef-' + EventTypeName)
    
    # Ideally, one would like to use an <interleave> pattern
    # here to define the mix of mandatory and optional objects.
    # However, since all objects have the same element name, 
    # this cannot be done. Interleave patterns don't allow it.
    # For now, we just check if all objects have a property
    # name that is allowed for the relevant event type.
    
    self.OpenElementRelaxNG('element').set('name', 'event')
    self.OpenElementRelaxNG('oneOrMore')
      
    self.OpenElementRelaxNG('element').set('name', 'object')
    self.OpenElementRelaxNG('attribute').set('name', 'property')
    self.OpenElementRelaxNG('choice')
      
    for PropertyName in self.GetEventTypeProperties(EventTypeName):
      self.OpenElementRelaxNG('value').set('type', 'string')
      self.CurrentElementRelaxNG.text = PropertyName
      self.CloseElementRelaxNG()
      
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.OpenElementRelaxNG('attribute').set('name', 'value')
    self.OpenElementRelaxNG('data').set('type', 'string')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()

    self.CloseElementRelaxNG()
    
    self.OpenElementRelaxNG('optional')
    self.OpenElementRelaxNG('element').set('name', 'content')
    self.OpenElementRelaxNG('text')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.CloseElementRelaxNG()
    
    self.CloseElementRelaxNG()
    return
    
  def GenerateGenericSourcesRelaxNG(self):
    """Generates a RelaxNG fragment representing an event source. Can be useful for
    generating modular RelaxNG schemas or constructing full
    EDXML validation schemas.
    
    Make sure to call OpenRelaxNG() first.
    
    """
    
    self.OpenElementRelaxNG('element').set('name', 'source')
    self.OpenElementRelaxNG('attribute').set('name', 'source-id')
    self.OpenElementRelaxNG('data').set('type', 'token')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.OpenElementRelaxNG('attribute').set('name', 'url')
    self.OpenElementRelaxNG('data').set('type', 'token')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.OpenElementRelaxNG('attribute').set('name', 'description')
    self.OpenElementRelaxNG('data').set('type', 'normalizedString')
    self.OpenElementRelaxNG('param').set('name', 'maxLength')
    self.CurrentElementRelaxNG.text = '128'
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.OpenElementRelaxNG('attribute').set('name', 'date-acquired')
    self.OpenElementRelaxNG('data').set('type', 'normalizedString')
    self.OpenElementRelaxNG('param').set('name', 'maxLength')
    self.CurrentElementRelaxNG.text = '8'
    self.CloseElementRelaxNG()
    self.OpenElementRelaxNG('param').set('name', 'pattern')
    self.CurrentElementRelaxNG.text = '[0-9]{8}'
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()

  def GenerateFullRelaxNG(self, EventRefs = None, EventTypeRefs = None, ObjectTypeRefs = None):
    """Generates a full RelaxNG schema, containing all known definitions
    of event types, object types and sources. You can optionally
    provide dictionaries which map event type names or object type names
    to URIs. In this case, the resulting schema will refer to these URIs
    in stead of generating the schema patterns in place. This might be
    useful if you have a central storage for event type definitions or
    object type definitions.
    
    Make sure to call OpenRelaxNG() first.
    
    Parameters:
    
    EventRefs      -- Optional dictionary containing URI of event schema for every event type name
    EventTypeRefs  -- Optional dictionary containing URI of event type schema for every event type name
    ObjectTypeRefs -- Optional dictionary containing URI of object type schema for every object type name
    
    """
    
    self.SchemaRelaxNG = etree.Element('element')
    self.SchemaRelaxNG.set('name', 'events')
    self.SchemaRelaxNG.set('xmlns', 'http://relaxng.org/ns/structure/1.0')
    self.SchemaRelaxNG.set('datatypeLibrary', 'http://www.w3.org/2001/XMLSchema-datatypes')
    self.CurrentElementRelaxNG = self.SchemaRelaxNG
    
    self.OpenElementRelaxNG('element').set('name', 'definitions')
    
    self.OpenElementRelaxNG('element').set('name', 'eventtypes')
    self.OpenElementRelaxNG('oneOrMore')
    self.OpenElementRelaxNG('choice')

    if EventTypeRefs == None:
      for EventTypeName in self.GetEventTypeNames():
        self.GenerateEventTypeRelaxNG(EventTypeName)
    else:
      for EventTypeName in self.GetEventTypeNames():
        self.OpenElementRelaxNG('externalRef').set('href', EventTypeRefs[EventTypeName])
        self.CloseElementRelaxNG()
      
    
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.OpenElementRelaxNG('element').set('name', 'objecttypes')
    self.OpenElementRelaxNG('oneOrMore')
    self.OpenElementRelaxNG('choice')
    
    if ObjectTypeRefs == None:
      for ObjectTypeName in self.GetObjectTypeNames():
        self.GenerateObjectTypeRelaxNG(ObjectTypeName)
    else:
      for ObjectTypeName in self.GetObjectTypeNames():
        self.OpenElementRelaxNG('externalRef').set('href', ObjectTypeRefs[ObjectTypeName])
        self.CloseElementRelaxNG()
      
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.OpenElementRelaxNG('element').set('name', 'sources')
    self.OpenElementRelaxNG('oneOrMore')
    
    self.GenerateGenericSourcesRelaxNG()
      
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.CloseElementRelaxNG()

    self.OpenElementRelaxNG('element').set('name', 'eventgroups')
    self.OpenElementRelaxNG('zeroOrMore')
    self.OpenElementRelaxNG('element').set('name', 'eventgroup')
    self.OpenElementRelaxNG('attribute').set('name', 'event-type')
    self.OpenElementRelaxNG('data').set('type', 'token')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.OpenElementRelaxNG('attribute').set('name', 'source-id')
    self.OpenElementRelaxNG('data').set('type', 'token')
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    self.OpenElementRelaxNG('zeroOrMore')
    self.OpenElementRelaxNG('choice')
    
    if EventRefs == None:
      for EventTypeName in self.GetEventTypeNames():
        self.GenerateEventRelaxNG(EventTypeName)
    else:
      for EventTypeName in self.GetEventTypeNames():
        self.OpenElementRelaxNG('externalRef').set('href', EventRefs[EventTypeName])
        self.CloseElementRelaxNG()
    
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    
    
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    self.CloseElementRelaxNG()
    