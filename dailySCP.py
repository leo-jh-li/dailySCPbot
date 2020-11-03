import random
import urllib
import os
import re
import time
import constants
import config
import schedule
import tweepy
from SCP import SCP, NoNameException, NoOclassException, UnknownSeriesException

auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
api = tweepy.API(auth_handler=auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)


def formatDesignation(designation):
    '''
    Formats an int or str designation into an SCP format str. Leading zeroes
    are added, if necessary.

    Args:
        designation: The potential designation.

    Returns:
        The designation as an SCP format str.
    '''
    formattedStr = str(designation)
    while len(formattedStr) < 3:
        formattedStr = '0' + formattedStr
    return formattedStr


def reportError(error, designation=None, status=None):
    '''
    Lets the creator know he messed up.

    Args:
        designation: The designation of the SCP that caused the error.
        error: The error message.
    '''
    report = ''
    if designation is not None:
        report += 'Anomalous entry: SCP-' + str(designation) + '\n'
    report = 'Error: ' + error
    if status is not None:
        report += '\nUser: ' + status.user.screen_name
        report += '\nTweet:\n' + status.text
    print(report)
    api.send_direct_message(user_id=config.INCIDENT_RECIPIENT_ID, text=report)


def removeAllImages():
    [os.remove(constants.IMAGES_DIR + '/' + f) for f in os.listdir(constants.IMAGES_DIR)]


def postSCP(designation):
    ''' Posts the SCP of the given designation. '''
    designation = formatDesignation(designation)
    try:
        scp = SCP(designation)
        print(scp)
        imagePath = scp.getImagePath()
        if imagePath:
            api.update_with_media(imagePath, status=scp.getCompleteStr())
            try:
                os.remove(imagePath)
            except OSError:
                pass
        else:
            api.update_status(scp.getCompleteStr())
    except (urllib.error.HTTPError, NoNameException, NoOclassException,
            UnknownSeriesException) as err:
        reportError(str(err), designation)
        raise PostSCPFailureException(str(err))


def postRandomSCP():
    ''' Posts a random SCP. '''
    num = str(random.randrange(1, constants.SCP_ENTRIES + 1))
    num = formatDesignation(num)
    postSCP(num)


def replyWithSCP(designation, status):
    ''' Tries to answer a request for information on an SCP. '''
    if designation is not None:
        formattedDesignation = formatDesignation(designation)
        mention = '@' + status.user.screen_name + ' '
        try:
            scp = SCP(formattedDesignation)
            print('Replied to ' + status.user.screen_name + ':\n' +
                  status.text + '\n'
                  'with:\n' +
                  str(scp))
            imagePath = scp.getImagePath()
            if imagePath:
                api.update_with_media(imagePath, status=mention + str(scp), in_reply_to_status_id=status.id_str)
                try:
                    os.remove(imagePath)
                except OSError:
                    pass
            else:
                api.update_status(mention + str(scp), in_reply_to_status_id=status.id_str)
        except (urllib.error.HTTPError, UnknownSeriesException) as err:
            reportError(str(err), designation, status)
            errorStatus = (mention + 'SCP-' + str(designation).upper() + ' - [ACCESS DENIED]\n'
                           'Object Class: [DATA EXPUNGED]\n'
                           'http://scp-wiki.net/scp-\u2588\u2588\u2588\u2588')
            api.update_status(errorStatus, in_reply_to_status_id=status.id_str)


def extractSCPDesignation(statusText):
    '''
    Gets the designation from text that may mention an SCP.

    Returns:
        The SCP's designation, or None if an appropriate one could not be
        found.
    '''
    statusText = removeMention(statusText)
    scps = re.findall('SCP-[a-zA-Z0-9-]+', statusText, re.IGNORECASE)
    if len(scps) == 1:
        return scps[0][4:]
    randIndex = re.findall('random', statusText, re.IGNORECASE)
    if len(randIndex) > 0:
        randIndex = random.randrange(1, constants.SCP_ENTRIES + 1)
        return randIndex
    if len(scps) == 0:
        dashlessScps = re.findall('SCP[a-zA-Z0-9-]+', statusText, re.IGNORECASE)
        spaceScps = re.findall('SCP [a-zA-Z0-9-]+', statusText, re.IGNORECASE)
        if len(dashlessScps) + len(spaceScps) == 1:
            if len(dashlessScps) == 1:
                return dashlessScps[0][3:]
            if len(spaceScps) == 1:
                return spaceScps[0][4:]
    return None


def removeMention(statusText):
    '''
    Removes the mention of the bot from the given text.

    Returns:
        The text without the @DailySCP.
    '''
    mentionIndex = statusText.lower().find(constants.BOT_HANDLE)
    if mentionIndex >= 0:
        statusText = statusText[:mentionIndex] + statusText[mentionIndex + len(constants.BOT_HANDLE):]
    return statusText


class PostSCPFailureException(Exception):
    '''
    Raised if an HTTPError, NoNameException, NoOclassException, or
    UnknownSeriesException occurs while trying to post an SCP.
    '''
    pass


class SCPStreamListener(tweepy.StreamListener):
    def on_status(self, status):
        designation = extractSCPDesignation(status.text)
        if designation is not None:
            replyWithSCP(designation, status)
        else:
            reportError('Unable to parse SCP from user tweet.', designation, status)

    def on_error(self, statusCode):
        if statusCode == 420:
            return False

streamListener = SCPStreamListener()
stream = tweepy.Stream(auth=api.auth, listener=streamListener)
stream.filter(track=['@DailySCP'], is_async=True)


def scheduledPost(firstAttempt=True):
    '''
    Attempts to do scheduled task. If it fails too many times, it tries again
    after a certain period of time.
    '''
    attempts = 0
    while attempts < constants.MAX_POST_ATTEMPTS:
        try:
            postRandomSCP()
            break
        except PostSCPFailureException:
            attempts += 1
        # if failed 100 times, sleep for 6 hrs and try again
        if attempts >= constants.MAX_POST_ATTEMPTS and firstAttempt:
            reportError('Failed to post 10 consecutive times.')
            time.sleep(constants.FAILURE_SLEEP_DURATION)
            print('Trying again...')
            scheduledPost(False)

schedule.every().day.at(constants.POST_TIME_UTC).do(scheduledPost)

while True:
    schedule.run_pending()
    time.sleep(60)
