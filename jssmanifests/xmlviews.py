from django.shortcuts import render
from django.http import HttpResponse, HttpRequest, HttpResponseRedirect

from django.conf import settings

from operator import attrgetter

import re

from manifests.models import Manifest

from jssmanifests.models import JSSComputerAttributeType
from lxml import etree

import jss
import plistlib

def manifest(request, manifest_name):

    if request.method == 'GET':

        # load base manifest from file system (either a specific one or site_default)
        manifest = Manifest.read(manifest_name)
        if not manifest:
            manifest = Manifest.read('site_default')

        # Only if the request matches an UDID (v4) the JSS will be queried
        if re.search('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', manifest_name.lower()):
            jss_connection = jss.JSS(user=settings.JSS_READONLY_USER,
                                 password=settings.JSS_READONLY_PASS,
                                 url=settings.JSS_URL,
                                 ssl_verify=settings.JSS_VERIFY_CERT)

            jcomputer = jss_connection.Computer('udid=%s' % manifest_name.upper())
            computer = etree.fromstring(jcomputer.__str__())
       
            if settings.JSSMANIFESTS_DEBUG_DUMPJSSEA:
                _dump_computer_ea(manifest, computer.iter('extension_attribute') )
            attribute_types = JSSComputerAttributeType.objects.all()

            manifest['computer_matches'] = []
            manifest_updates = []

            for type in attribute_types:
                if settings.JSSMANIFESTS_DEBUG_DUMPJSSEA:
                    type.dump_debug_xml(manifest)
                mappings = type.jsscomputerattributemapping_set.all()
                for mapping in mappings:
                    if mapping.computer_match(computer):
                        if settings.JSSMANIFESTS_DEBUG_DUMPJSSEA:
                            manifest['computer_matches'].append( '%s' % mapping)
                        manifest_updates.append(mapping)

            manifest_updates.sort( key=attrgetter('priority') )
            for manifest_update in manifest_updates:
                manifest_update.apply_mapping(manifest)

        response = HttpResponse(content_type='application/xml')
        plistlib.writePlist(manifest, response)

        if settings.JSSMANIFESTS_DOWNLOAD_AS_ATTACHMENT:
            response['Content-Disposition'] = "attachment; filename=%s" % udid

    return response

def _dump_list(tag, manifest, attr_list):

    manifest[tag] = []

    for attr in attr_list:
        name = attr.find('name').text
        val  = '(undef)'

        if attr.find('value').text:
            val = attr.find('value').text

        manifest[ tag ].append("%s = %s" % ( name, val) )

def _dump_computer_ea(manifest, attr_list):

    _dump_list('jss_extension_attributes', manifest, attr_list)

