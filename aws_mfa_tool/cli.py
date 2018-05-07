import click
import boto3
import os
import random
import string
import ConfigParser
import sys

from getpass import getpass


@click.group()
def cli():
    pass


@cli.command(
    'create',
    help='Gets STS session token')
@click.option(
    '-r', '--region',
    help='AWS region')
@click.option(
    '-p', '--profile',
    help='AWS shared credentials profile')
@click.option(
    '-m', '--mfa-serial',
    help='MFA serial ARN')
@click.option(
    '-t', '--token-code',
    help='MFA token code. If this is ommitted and --mfa-serial is given, '
         'you will be prompted for a code')
@click.option(
    '-d', '--duration', default=86400,
    help='STS token TTL in seconds')
@click.option(
    '-o', '--save-output-profile',
    help='Shared credentials profile name to be written / overwritten')
@click.option(
    '-s', '--skip-save',
    is_flag=True,
    help='Skip save to shared credentials')
@click.option(
    '-j', '--display-json',
    is_flag=True,
    help='Display JSON response from the AWS API')
def create(
    region,
    profile,
    mfa_serial,
    duration,
    token_code,
    skip_save,
    save_output_profile,
    display_json
):
    session = boto3.Session(
        profile_name=profile,
        region_name=region)
    client = session.client('sts')

    params = {}

    if mfa_serial is not None:
        # MFA ARN passed as an option
        params['SerialNumber'] = mfa_serial
    else:
        # MFA ARN not passed as an option. Attempt to fetch from profile.
        mfa_serial = get_mfa_arn(profile);

        if mfa_serial is not None:
             params['SerialNumber'] = mfa_serial
        else:
             print "Unable to find MFA for profile " + profile + "."
             print "Configure MFA ARN in ~/.aws/config or pass it with the --mfa-serial option."
             sys.exit()

    if duration is not None:
        params['DurationSeconds'] = duration

    if token_code is not None:
        params['TokenCode'] = token_code
    else:
        params['TokenCode'] = getpass('Input MFA code: ')

    response = client.get_session_token(**params)

    if not skip_save:
        if save_output_profile is None:
            save_output_profile = '_{}'.format(profile)

        aws_secret_access_key = response['Credentials']['SecretAccessKey']
        aws_access_key_id = response['Credentials']['AccessKeyId']
        aws_session_token = response['Credentials']['SessionToken']

        write_profile(save_output_profile,  {
            'aws_secret_access_key': aws_secret_access_key,
            'aws_access_key_id': aws_access_key_id,
            'aws_session_token': aws_session_token,
        })

    if display_json is not False:
        print response


@cli.command(
    'assume-role',
    help='STS assume role')
@click.option(
    '-r', '--region',
    help='AWS region')
@click.option(
    '-p', '--profile',
    default='default',
    help='AWS shared credentials profile')
@click.option(
    '-r', '--role-arn',
    help='AWS shared credentials profile')
@click.option(
    '-f', '--from-profile',
    help='Name of profile from where the Role ARN should be fetched')
@click.option(
    '--role-session-name',
    help='AWS shared credentials profile')
@click.option(
    '-m', '--mfa-serial',
    help='MFA serial ARN')
@click.option(
    '-t', '--token-code',
    help='MFA token code. If this is ommitted and --mfa-serial is given, '
         'you will be prompted for a code')
@click.option(
    '-d', '--duration',
    default=28800,
    help='STS token TTL in seconds')
@click.option(
    '-o', '--save-output-profile',
    help='Shared credentials profile name to be written / overwritten')
@click.option(
    '-s', '--skip-save',
    is_flag=True,
    help='Skip save to shared credentials')
@click.option(
    '-j', '--display-json',
    is_flag=True,
    help='Display JSON response from the AWS API')
def create(
    region,
    profile,
    role_arn,
    from_profile,
    role_session_name,
    mfa_serial,
    duration,
    token_code,
    skip_save,
    save_output_profile,
    display_json
):
    session = boto3.Session(
        profile_name=profile,
        region_name=region)
    client = session.client('sts')

    params = {}

    if role_arn is not None:
        params['RoleArn'] = role_arn
    else:
        # Fetch Role ARN from the given profile in the config file
        if from_profile is not None:
            params['RoleArn'] = get_role_arn_by_profile(from_profile)
        else:
            print "Either -r/--role_arn or -f/--from_profile must be given.\n"
            sys.exit()


    if mfa_serial is not None:
        # MFA ARN passed as an option
        params['SerialNumber'] = mfa_serial
    else:
        # MFA ARN not passed as an option. Attempt to fetch from profile.
        mfa_arn = get_mfa_arn(profile);

        params['SerialNumber'] = get_mfa_arn(profile)
        if params['SerialNumber'] is None:
             print "Unable to find MFA for profile " + profile + "."
             print "Configure MFA ARN in ~/.aws/config or pass it with the --mfa-serial option."
             sys.exit()

    if duration is not None:
        params['DurationSeconds'] = duration

    if token_code is not None:
        params['TokenCode'] = token_code
    else:
        params['TokenCode'] = getpass('Input MFA code: ')

    if role_session_name is None:
        params['RoleSessionName'] = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(16))
    else:
        params['RoleSessionName'] = role_session_name

    response = client.assume_role(**params)

    if not skip_save:
        if save_output_profile is None:
            save_output_profile = '_{}'.format(profile)

        aws_secret_access_key = response['Credentials']['SecretAccessKey']
        aws_access_key_id = response['Credentials']['AccessKeyId']
        aws_session_token = response['Credentials']['SessionToken']

        write_profile(save_output_profile,  {
            'aws_secret_access_key': aws_secret_access_key,
            'aws_access_key_id': aws_access_key_id,
            'aws_session_token': aws_session_token,
        })

    if display_json is not False:
        print response


def write_profile(profile, values):
    configure_frm = 'aws configure --profile {aws_profile} set {name} {value}'

    for name, value in values.iteritems():
        os.system(configure_frm.format(
            aws_profile=profile,
            name=name,
            value=value,
        ))

    print 'Saved credentials profile "{}"!'.format(profile)


def get_mfa_arn(current_profile_name):
    config_parser = ConfigParser.ConfigParser()
    config_parser.read(os.path.expanduser('~/.aws/config'))

    for section in config_parser.sections():
        section_parts = section.split(' ')

        # Check if this section of the config looks like a profile, and if
        # it's the profile we're after:
        if 1 < len(section_parts):
            if section_parts[0] == 'profile':
                if section_parts[1] == current_profile_name:
                    data = dict(config_parser.items(section))
                    mfa_arn = data.get("mfa_serial")
                    return mfa_arn

    return None


def get_role_arn_by_profile(from_profile):
    config_parser = ConfigParser.ConfigParser()
    config_parser.read(os.path.expanduser('~/.aws/config'))

    for section in config_parser.sections():
        section_parts = section.split(' ')

        # Check if this section of the config looks like a profile, and if
        # it's the profile we're after:
        if 1 < len(section_parts):
            if section_parts[0] == 'profile':
                if section_parts[1] == from_profile:
                    data = dict(config_parser.items(section))
                    role_arn = data.get("role_arn")
                    return role_arn

    return None


if __name__ == '__main__':
    cli()
