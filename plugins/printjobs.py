'''
   Copyright (c) 2017 Yogesh Khatri 

   This file is part of mac_apt (macOS Artifact Parsing Tool).
   Usage or distribution of this software/code is subject to the 
   terms of the MIT License.

   printjobs.py
   ------------
   This plugin will parse information about documents that were printed. The 
   information is in the form of CUPS (Common UNIX Printing System)
   print job data located at /private/var/spool/cups
'''

from __future__ import print_function
from __future__ import unicode_literals
from pkipplib import pkipplib
import datetime
from helpers.macinfo import *
from helpers.writer import *
from helpers.common import *
import logging
import os

__Plugin_Name = "PRINTJOBS" # Cannot have spaces, and must be all caps!
__Plugin_Friendly_Name = "Print job info"
__Plugin_Version = "1.0"
__Plugin_Description = "Parses CUPS spooled print jobs to get information about files/commands sent to a printer"
__Plugin_Author = "Jack Farley, Yogesh Khatri"
__Plugin_Author_Email = "jack.farley@mymail.champlain.edu, yogesh@swiftforensics.com"

__Plugin_Standalone = True
__Plugin_Standalone_Usage = 'Parses print jobs from the provided folder. You must supply path to the /private/var/spool/cups folder'

log = logging.getLogger('MAIN.' + __Plugin_Name) # Do not rename or remove this ! This is the logger object

#---- Do not change the variable names in above section ----#

def PrintAll(cups_list, output_params, source_path):

    cups_info = [ ('Job',DataType.TEXT),('Owner',DataType.TEXT),('Job ID',DataType.INTEGER),
                    ('Destination Printer', DataType.TEXT),('Application',DataType.TEXT),('Time of Creation',DataType.DATE),
                    ('Time at Processing',DataType.DATE),('Time of Competion',DataType.DATE),
                    ('Copies', DataType.INTEGER),('Document Format', DataType.TEXT),
                    ('Origin Host Name', DataType.TEXT),('State', DataType.TEXT),('Sheets printed', DataType.INTEGER),
                    ('Printer state msg', DataType.TEXT),('Printer state reason', DataType.TEXT),('PrinterURI',DataType.TEXT),
                    ('Job UUID',DataType.TEXT),('Cached_File',DataType.TEXT),('Source',DataType.TEXT)
                ]

    log.info (str(len(cups_list)) + " print job(s) found")
    WriteList("print job information", "Print Jobs", cups_list, cups_info, output_params, source_path)

def Plugin_Start(mac_info):
    '''Main Entry point function for plugin'''
    cupsDirectory = '/private/var/spool/cups'
    #cacheDirectory = cupsDirectory + '/cache'
    #tmpDirectory = cupsDirectory + '/tmp'

    jobs = []
    files_list = mac_info.ListItemsInFolder(cupsDirectory, EntryType.FILES)
    for item in files_list:
        filename = item['name']
        filepath = cupsDirectory + '/' + filename
        if filename.startswith('c') and item['size'] > 0:
            mac_info.ExportFile(filepath, __Plugin_Name)
            cups_info = parse_cups_file_from_image(mac_info, filepath)
            if cups_info:
                jobs.append(cups_info)
    # Now look for d00xxx files, these are cached files corresponding to job-ids
    for item in files_list:
        filename = item['name']
        filepath = cupsDirectory + '/' + filename
        if filename.startswith('d') and item['size'] > 0:
            mac_info.ExportFile(filepath, __Plugin_Name)
            # Get job id from name
            job_id = 0
            job_id_str = filename[1:]
            dash_pos =job_id_str.find('-')
            if dash_pos > 0:
                job_id_str = job_id_str[0:dash_pos]
            job_id = CommonFunctions.IntFromStr(job_id_str)
            # Find the entry that represents that job id
            cups_info = None
            for job in jobs:
                if job[2] == job_id:
                    cups_info = job
                    break
            if cups_info: # Found job
                cups_info[17] = filename
            else: # Did not find job, create new one
                jobs.append(['', '', None, '', '', '', '', '', '', '', '', '', '', '', '', None, '', filename, ''])
    if jobs:
        PrintAll(jobs, mac_info.output_params, cupsDirectory)

def get_job_detail(request, job_request, ret_all_replies=False, ret_on_error=''):
    '''Returns the specific data requested in job_request. If ret_all_replies=True, a list is returned'''
    try:
        replies = request.job[job_request]
        if ret_all_replies:
            return [reply[1] for reply in replies]
        else:
            return replies[0][1]

    except Exception as ex:
        print ('Error retrieving value for ' + job_request)
    if ret_all_replies: return []
    return ret_on_error

def get_job_state_str(state):
    if state == 3: return 'JOB_PENDING'
    elif state == 4: return 'JOB_HELD'
    elif state == 5: return 'JOB_PROCESSING'
    elif state == 6: return 'JOB_STOPPED'
    elif state == 7: return 'JOB_CANCELLED'
    elif state == 8: return 'JOB_ABORTED'
    elif state == 9: return 'JOB_COMPLETE'
    else:
        return str(state)

def get_job_properties(request, filepath):
    '''Get job properties from request object'''
    job_name = get_job_detail(request, "job-name").decode("utf8")
    job_origin_username = get_job_detail(request, "job-originating-user-name").decode("utf8")
    printer_uri = get_job_detail(request, "printer-uri").decode("utf8")
    doc_format = get_job_detail(request, "document-format").decode("utf8")
    job_ID = get_job_detail(request, "job-id")
    job_origin_hostname = get_job_detail(request, "job-originating-host-name").decode("utf8")
    job_uuid = get_job_detail(request, "job-uuid").decode("utf8")
    job_state = get_job_state_str(get_job_detail(request, "job-state"))
    job_printer_state_message = get_job_detail(request, "job-printer-state-message").decode("utf8")
    reasons = get_job_detail(request, "job-printer-state-reasons", ret_all_replies=True)
    job_printer_state_reason = ', '.join([reason.decode("utf8") for reason in reasons])
    job_media_sheets_completed = get_job_detail(request, "job-media-sheets-completed")

    copies = get_job_detail(request, "copies")
    destination_printer = get_job_detail(request, "DestinationPrinterID").decode("utf8")
    app = get_job_detail(request, "com.apple.print.JobInfo.PMApplicationName").decode("utf8")

    time_at_creation = CommonFunctions.ReadUnixTime(get_job_detail(request, "time-at-creation"))
    time_at_processing = CommonFunctions.ReadUnixTime(get_job_detail(request, "time-at-processing"))
    time_at_completion = CommonFunctions.ReadUnixTime(get_job_detail(request, "time-at-completed"))

    return [job_name, job_origin_username, job_ID, destination_printer, app, time_at_creation, time_at_processing, time_at_completion,\
             copies, doc_format, job_origin_hostname, job_state, job_media_sheets_completed, job_printer_state_message,\
             job_printer_state_reason, printer_uri, job_uuid, '',filepath]

def parse_cups_file_from_image(mac_info, filepath):
    '''Process individual job file (c00xxx) and return list of properties'''
    j_file = mac_info.OpenSmallFile(filepath)
    if j_file != None:
        ippdatas = j_file.read()
        request = pkipplib.IPPRequest(ippdatas)
        request.parse()
        j_file.close()
    else:
        log.error ('Error parsing cups job file ' + filepath + ' Error=' + str(ex))
        return None
    return get_job_properties(request, filepath)

def parse_cups_file(filepath):
    '''Process individual job file (c00xxx) and return list of properties'''
    try:
        with open(filepath, 'rb') as j_file:
            ippdatas = j_file.read()
            request = pkipplib.IPPRequest(ippdatas)
            request.parse()
            j_file.close()
    except:
        log.exception ('Error opening cups job file ' + filepath)
        return None
    return get_job_properties(request, filepath)


def Plugin_Start_Standalone(input_files_list, output_params):
    log.info("Module Started as standalone")
    for input_path in input_files_list:
        log.debug("Input folder passed was: " + input_path)
        jobs = []
        try:
            dirList = os.listdir(input_path)
            had_exception = False
        except:
            log.exception('Problem listing files.. Is the path provided a file (instead of a folder)?')
            had_exception = True
        if not had_exception:
            for filename in dirList:
                filepath = os.path.join(input_path, filename)
                if os.path.isfile(filepath):
                    if filename.startswith('c'):
                        cups_info = parse_cups_file(filepath)
                        if cups_info:
                            jobs.append(cups_info)
            # Now look for d00xxx files, these are cached files corresponding to job-ids
            for filename in dirList:
                filepath = os.path.join(input_path, filename)
                if filename.startswith('d'):
                    # Get job id from name
                    job_id = 0
                    job_id_str = filename[1:]
                    dash_pos =job_id_str.find('-')
                    if dash_pos > 0:
                        job_id_str = job_id_str[0:dash_pos]
                    job_id = CommonFunctions.IntFromStr(job_id_str)
                    # Find the entry that represents that job id
                    cups_info = None
                    for job in jobs:
                        if job[2] == job_id:
                            cups_info = job
                            break
                    if cups_info: # Found job
                        cups_info[17] = filename
                    else: # Did not find job, create new one
                        jobs.append(['', '', None, '', '', '', '', '', '', '', '', '', '', '', '', None, '', filename, ''])

        if len(jobs) > 0:
            PrintAll(jobs, output_params, filepath)
        else:
            log.info('No print jobs found in {}'.format(input_path))

if __name__ == '__main__':
    print ("This plugin is a part of a framework and does not run independently on its own!")