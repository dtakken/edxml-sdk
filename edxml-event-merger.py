#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#
#  ===========================================================================
# 
#                            EDXML Event Merger
#
#                            EXAMPLE APPLICATION
#
#                  Copyright (c) 2010 - 2016 by D.H.J. Takken
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
#
#  This script reads an EDXML stream from standard input or from a file and outputs
#  that same stream after resolving event hash collisions in the input. Every time an
#  input event collides with a preceding event, the event will be merged and an updated
#  version is output. That means that the number of output events equals the number of
#  input events.
#
#  Note that, unless buffering is used, this script needs to store one event for each
#  sticky hash of the input events in RAM. For large event streams that contain events
#  with many different sticky hashes, it will eventually run out of memory. Extending
#  this example to use an external storage backend in order to overcome this limitation
#  is left as an exercise to the user.

import sys
import time
from StringIO import StringIO
from xml.sax import make_parser
from xml.sax.saxutils import XMLGenerator
from edxml.EDXMLWriter import EDXMLWriter
from edxml.EDXMLFilter import EDXMLEventEditor
from edxml.EDXMLParser import EDXMLParser

# We create a class based on EDXMLEventEditor,
# overriding the EditEvent to process
# the events in the EDXML stream.

class EDXMLEventMerger(EDXMLEventEditor):

  def __init__ (self, upstream):

    EDXMLEventEditor.__init__(self, upstream)
    self.HashBuffer = {}

  # Override of EDXMLEventEditor implementation
  def EditEvent(self, SourceId, EventTypeName, EventObjects, EventContent, EventAttributes):

    # Use the EDXMLDefinitions instance in the 
    # EDXMLEventEditor class to compute the sticky hash
    Hash = self.Definitions.ComputeStickyHash(EventTypeName, EventObjects, EventContent)

    Properties = [Object['property'] for Object in EventObjects]
    EventProperties = {Property: [Object['value'] for Object in EventObjects if Object['property'] == Property] for Property in Properties}

    if Hash in self.HashBuffer:
      self.Definitions.MergeEvents(EventTypeName, self.HashBuffer[Hash]['Objects'], EventProperties)

      EventObjects = []
      for Property, Values in self.HashBuffer[Hash]['Objects'].items():
        for Value in Values:
          EventObjects.append({'property': Property, 'value': Value})
    else:
      self.HashBuffer[Hash] = {
        'Objects': EventProperties
      }

    return EventObjects, EventContent, EventAttributes

# We create another, slightly more complicated
# class, based on EDXMLParser, overriding multiple
# parent methods to buffer input events and generate
# merged output events. By extending the low level
# EDXMLParser in stead of the high level EDXMLEventEditor,
# we have more control over the output.

class BufferingEDXMLEventMerger(EDXMLParser):

  def __init__ (self, EventBufferSize, Latency, upstream):

    self.BufferSize = 0
    self.MaxLatency = Latency
    self.MaxBufferSize = EventBufferSize
    self.LastOutputTime = time.time()
    self.Buffer = {}

    # Create a parser for the input.
    EDXMLParser.__init__(self, upstream)

    # Create a generator for outputting EDXML.
    self.Generator = EDXMLWriter(sys.stdout)

  def DefinitionsLoaded(self):

    # All definitions in the input have been read
    # and parsed. We can regenerate the XML representation
    # of the definitions and inject that into the EDXML
    # generator, effectively duplicating the input
    # definitions into the output.
    DefinitionsElement = StringIO()
    self.Definitions.GenerateXMLDefinitions(XMLGenerator(DefinitionsElement, 'utf-8'))
    self.Generator.AddXmlDefinitionsElement(DefinitionsElement.getvalue())
    self.Generator.OpenEventGroups()

  def ProcessEvent(self, EventTypeName, SourceId, EventObjects, EventContent, Parents):

    # An input event has been read and parsed. We buffer these
    # events per event group, to allow outputting multiple events
    # per event group.
    Group = '%s:%s' % (EventTypeName, SourceId)
    if not Group in self.Buffer:
      self.Buffer[Group] = {}

    # Use the EDXMLDefinitions instance in the
    # EDXMLEventEditor class to compute the sticky hash
    Hash = self.Definitions.ComputeStickyHash(EventTypeName, EventObjects, EventContent)

    # Group event objects by property.
    Properties = [Object['property'] for Object in EventObjects]
    EventProperties = {Property: [Object['value'] for Object in EventObjects if Object['property'] == Property] for Property in Properties}

    if Hash in self.Buffer[Group]:
      # This hash is in our buffer, which means
      # we have a collision. Merge input event
      # into the buffered event.
      self.Definitions.MergeEvents(EventTypeName, self.Buffer[Group][Hash]['Objects'], EventProperties)
    else:
      # We have a new hash, add it to
      # the buffer.
      self.Buffer[Group][Hash] = {
        'EventTypeName': EventTypeName,
        'SourceId': SourceId,
        'Objects': EventProperties,
        'EventContent': EventContent,
        'Parents': Parents
      }

      self.BufferSize += 1
      if self.BufferSize >= self.MaxBufferSize:
        self.FlushBuffer()

    if self.BufferSize > 0 and self.MaxLatency > 0 and (time.time() - self.LastOutputTime) >= self.MaxLatency:
      self.FlushBuffer()

  def EndOfStream(self):
    self.FlushBuffer()
    self.Generator.CloseEventGroups()

  def FlushBuffer(self):

    # Traverse the event buffer, output events
    # per event group.
    for Group, Events in self.Buffer.items():
      EventTypeName, SourceId = Group.split(':')
      self.Generator.OpenEventGroup(EventTypeName, SourceId)
      for Hash, Event in Events.items():
        self.Generator.AddEvent(Event['Objects'], Event['EventContent'], Event['Parents'])
      self.Generator.CloseEventGroup()

    self.BufferSize = 0
    self.LastOutputTime = time.time()
    self.Buffer = {}

def PrintHelp():

  print """

   This utility reads an EDXML stream from standard input or from a file and outputs
   that same stream after resolving event hash collisions in the input.

   Options:

     -h, --help        Prints this help text

     -f                This option must be followed by a filename, which
                       will be used as input. If this option is not specified,
                       input will be read from standard input.

     -b                By default, input events are not buffered, which means that
                       every input event is either passed through unmodified or
                       results in a merged version of input event. By setting this
                       option to a positive integer, the specified number of input
                       events will be buffed and merged when the buffer is full. That
                       means that, depending on the buffer size, the number of output
                       events may be significantly reduced.

     -l                When input events are buffered, input event streams having low
                       event throughput may result in output streams that stay silent
                       for a long time. Setting this option to a number of (fractional)
                       seconds, the output latency can be controlled, forcing it to
                       flush its buffer at regular intervals.
   Example:

     edxml-event-merger.py -b 1000 -l 10 -f input.edxml > output.edxml

"""

CurrOption = 1
BufferSize = 1
OutputLatency = 0
InputFileName = None

while CurrOption < len(sys.argv):

  if sys.argv[CurrOption] in ('-h', '--help'):
    PrintHelp()
    sys.exit(0)

  elif sys.argv[CurrOption] == '-f':
    CurrOption += 1
    InputFileName = sys.argv[CurrOption]

  elif sys.argv[CurrOption] == '-b':
    CurrOption += 1
    BufferSize = int(sys.argv[CurrOption])

  elif sys.argv[CurrOption] == '-l':
    CurrOption += 1
    OutputLatency = float(sys.argv[CurrOption])

  else:
    sys.stderr.write("Unknown commandline argument: %s\n" % sys.argv[CurrOption])
    sys.exit()

  CurrOption += 1

# Create a SAX parser, and provide it with
# an EDXMLEventMerger instance as content handler.
# This places the EDXMLEventMerger instance in the
# XML processing chain, just after SaxParser.

if BufferSize > 1:
  # If a maximum latency is specified, we need to
  # use an incremental parser that we can feed.
  SaxParser = make_parser(['xml.sax.IncrementalParser'])
else:
  SaxParser = make_parser()

if BufferSize > 1:
  SaxParser.setContentHandler(BufferingEDXMLEventMerger(BufferSize, OutputLatency, SaxParser))
else:
  SaxParser.setContentHandler(EDXMLEventMerger(SaxParser))

if InputFileName is None:
  sys.stderr.write("\nNo filename was given, waiting for EDXML data on STDIN...(use --help to get help)")
  Input = sys.stdin
else:
  sys.stderr.write("\nProcessing file %s:" % InputFileName )
  Input = open(InputFileName)

sys.stdout.flush()

# Now we feed EDXML data into the Sax parser. This will trigger
# calls to ProcessEvent in our EDXMLEventMerger, producing output.

if BufferSize > 1:
  # We need to read input with minimal
  # input buffering. This works best
  # when using the readline() method.
  while 1:
    Line = Input.readline()

    if not Line:
      break

    SaxParser.feed(Line)
else:
  SaxParser.parse(Input)
