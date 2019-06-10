import os
import argparse

from requests import Session
from requests import packages

from flask import Flask, request, render_template, url_for, redirect, session, Response
from dotmap import DotMap

from zeep import Client
from zeep.transports import Transport

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(20))

verbose = False

ivanti_user = os.getenv('IVANTI_USER', 'Set IVANTI_USER to your Ivanti username')
ivanti_pass = os.getenv('IVANTI_PASS', 'Set IVANTI_PASS to your Ivanti password')
ivanti_tenant_id = os.getenv('IVANTI_TENANT_ID', 'Set IVANTI_TENANT_ID to your Ivanti tenant ID')
ivanti_role = os.getenv('IVANTI_ROLE', 'Set IVANTI_ROLE to your Ivanti role')

ivanti_default_incident_fields = {
    "OwnerTeam": os.getenv('IVANTI_DEFAULT_OWNERTEAM', 'No OwnerTeam'),
    "MA_GroupType": os.getenv('IVANTI_DEFAULT_MA_GROUPTYPE', 'No MA_GroupType'),
    "Service": os.getenv('IVANTI_DEFAULT_SERVICE', 'No Service'),
    "Category": os.getenv('IVANTI_DEFAULT_CATEGORY', 'No category'),
    "ProfileLink": os.getenv('IVANTI_DEFAULT_PROFILELINK', 'No ProfileLink')
}

ivanti_url = f"https://{ivanti_tenant_id}/ServiceAPI/FRSHEATIntegration.asmx?wsdl"

def get_client(url):
    session = Session()
    session.verify = False
    packages.urllib3.disable_warnings()
    transport = Transport(session=session)
    client = Client(url, transport=transport)
    return client

def createObjectCommandData(client, ObjectType, fields):
    if verbose:
        print("Creating ObjectCommandData of type: {}".format(ObjectType))
    object_command_data = client.get_type('ns0:ObjectCommandData')
    command_data = object_command_data()
    command_data.ObjectType = ObjectType

    command_data_array_type = client.get_type('ns0:ArrayOfObjectCommandDataFieldValue')
    command_data_array = command_data_array_type()
    command_data_notes_type = client.get_type('ns0:ObjectCommandDataFieldValue')
    for name in fields.keys():
        if verbose:
            print(f"\tadding {name} {fields[name]}")
        command_data_array['ObjectCommandDataFieldValue'].append(command_data_notes_type(Name=name, Value=fields[name]))
    command_data.Fields = command_data_array
    return command_data

def create_ivanti_incident(fields):
    client = get_client(ivanti_url)
    connect = client.service.Connect(ivanti_user, ivanti_pass, ivanti_tenant_id, ivanti_role)

    command_data = createObjectCommandData(client, "Incident#", {**ivanti_default_incident_fields, **fields})
    output = client.service.CreateObject(connect.sessionKey, ivanti_tenant_id, command_data)

    if verbose:
        print("CreateObject output:\n{}".format(output))

    if output.status == 'Success':
        print("Success!")
    else:
        print("Failed!")
        print("     status: {}".format(output.status))
        print("     exceptionReason: {}".format(output.exceptionReason))


@app.route("/pd_to_ivanti", methods=['POST'])
def pd_to_ivanti():
    req = DotMap(request.json)

    if isinstance(req.messages[0].event, str):
        event = req.messages[0].event
        if event == 'incident.custom' or event == 'incident.trigger':
            subject = f"PagerDuty: {req.messages[0].incident.title}"
            symptom = f'PagerDuty incident number <a href="{req.messages[0].incident.html_url}">{req.messages[0].incident.incident_number}</a>'
            create_ivanti_incident({
                "Subject": subject,
                "Symptom": symptom
            })

    return ('ok', 200)