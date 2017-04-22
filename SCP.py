import urllib.request
import re
import os
import requests
import constants
from bs4 import BeautifulSoup


class SCP:
    def __init__(self, num):
        url = 'http://www.scp-wiki.net/scp-' + num
        page = urllib.request.urlopen(url)
        self.entryHtml = BeautifulSoup(page, 'html.parser')
        self.designation = str(num).upper()
        self.anomalousName = False
        self.name = self.__extractName()
        self.url = url
        self.oclass = self.__extractObjectClass()
        self.__extractImage()

    def __extractName(self):
        '''
        Gets the SCP's name.

        Returns:
            The SCP's name, extracted from the series page.
        '''
        url = self.__getSeriesUrl()
        page = urllib.request.urlopen(url)
        html = BeautifulSoup(page, 'html.parser')
        item = html.find(href=re.compile('^/scp-' + self.designation + '$', re.IGNORECASE))
        if item is None:
            # find href that contains the SCP's number instead
            tags = html.find_all(href=re.compile(self.designation, re.IGNORECASE))
            if len(tags) == 1:
                item = tags[0]
            else:
                return None
        item.parent = removeStrikethrough(item.parent)
        return self.getNameFromListing(item.parent.get_text())

    def __extractObjectClass(self):
        ''' Gets the SCP's Object Class.

        Returns:
            The SCP's Object Class, extracted from its entry, or failing that,
            its tags.
        '''
        oclass = self.entryHtml.find('strong', string="Object Class:")
        if not oclass:
            # if searching the article fails us, scour tags for the Object Class instead
            oclass = self.__extractOclassFromTags()
            # if searching the tags fails us, search article again with different parameters
            if oclass is None:
                label = self.entryHtml.body.find(text=re.compile('Object Class:'))
                if label:
                    return getOclassFromTree(label.parent)
                else:
                    return None
            else:
                return oclass
        ret = getOclassFromTree(oclass.parent)
        if not verifyOclass(ret):
            # if this Object Class is not recognized, search tags instead
            return self.__extractOclassFromTags()
        return ret

    def __extractOclassFromTags(self):
        '''
        Searches the SCP's tags for its Object Class.

        Returns:
            The SCP's Object Class, extracted from its tags, or None if it
            could not be found.
        '''
        tags = self.entryHtml.find('div', {'class': 'page-tags'})
        if tags:
            for oclass in constants.VALID_OBJECT_CLASSES:
                if tags.find_all(string=oclass):
                    return oclass.capitalize()
        return None

    def __getSeriesUrl(self):
        '''
        Returns the URL of the series page on which this SCP is listed.

        Returns:
            The url of the relevant series page.
        '''
        try:
            num = int(self.designation)
            if num < 1:
                if num < 1000:
                    return 'http://www.scp-wiki.net/scp-series'
                if num < 2000:
                    return 'http://www.scp-wiki.net/scp-series-2'
                if num < 3000:
                    return 'http://www.scp-wiki.net/scp-series-3'
        except ValueError:
            if self.designation.lower().find('j') >= 0 or self.designation.lower().find('cu') >= 0:
                return 'http://www.scp-wiki.net/joke-scps'
            if self.designation.lower().find('ex') >= 0:
                return 'http://www.scp-wiki.net/scp-ex'
        raise UnknownSeriesException('Could not find series for SCP-' + self.designation + '.')

    def __extractImage(self):
        '''
        Downloads the SCP's image if one exists and sets the SCP's imageName
        appropriately.
        '''
        imgDiv = self.entryHtml.find('div', {'class': 'scp-image-block block-right'})
        if imgDiv:
            img = imgDiv.find('img')
            if img and img['src']:
                self.imagePath = constants.IMAGES_DIR + '/' + self.designation + '.jpg'
                request = requests.get(img['src'], stream=True)
                if request.status_code == 200:
                    os.makedirs(constants.IMAGES_DIR, exist_ok=True)
                    with open(self.imagePath, 'wb') as image:
                        for chunk in request:
                            image.write(chunk)
                        return
        self.imagePath = None

    def __str__(self):
        ret = ''
        if self.name is not None:
            if not self.anomalousName:
                ret += 'SCP-' + self.designation + ' - ' + self.name + '\n'
            else:
                ret += handleAnomalousName(self.name, self.designation)
        else:
            ret += 'SCP-' + self.designation + '\n'
        if self.oclass is not None:
            ret += 'Object Class: ' + self.oclass + '\n'
        ret += self.url
        return ret

    def getCompleteStr(self):
        '''
        Returns the str of the SCP only if it has a name and Object Class.

        Returns:
            The string representation of the SCP.

        Raises:
            NoNameException: If the name could not be found.
            NoOclassException: If no Object Class could not be found.
        '''
        if self.name is None:
            raise NoNameException('No name found for SCP-' + self.designation + '.')
        if self.oclass is None:
            raise NoOclassException('No Object Class found for SCP-' + self.designation + '.')
        return str(self)

    def getNameFromListing(self, string):
        '''
        Returns the input string without the leading "SCP-xxxx - ".

        Args:
            string: The str to format.

        Returns:
            The string without the number label, or if there is no number
            label, the same string, unmodified.
        '''
        dashFormat = '-'
        for _ in range(0, constants.DASHES_IN_LISTING):
            dashIndex = string.find(dashFormat)
            if dashIndex >= 0:
                string = string[dashIndex+len(dashFormat):]
            else:
                self.anomalousName = True
                return string.strip()
            dashFormat = ' - '
        string = string.strip()
        return string

    def getImagePath(self):
        return self.imagePath


def getOclassFromTree(tree):
    '''
    Gets the Object Class from a tree containing "Object Class: ...".

    Args:
        tree: A tree containing the HTML of the Object Class label.

    Returns:
        The Object Class, without the label or any other unrelated tags,
        as a str.
    '''
    tree = __removeNonOclassTags(tree)
    tree = __removeLabelFromOclass(tree.get_text())
    return tree


def __removeLabelFromOclass(string):
    '''
    Removes the "Object Class: " label from the given string.

    Args:
        string: A string of the format "Object Class: ______".

    Returns:
        The Object Class without the label.
    '''
    colonIndex = string.find(':')
    if colonIndex >= 0:
        string = string[colonIndex+1:].strip()
        return string
    else:
        return None


def removeStrikethrough(tree):
    '''
    Removes strickenthrough text in a tree.

    Args:
        tree: An HTML tree.

    Returns:
        The same tree, without any strickenthrough elements.
    '''
    spanTags = tree.findAll('span', style='text-decoration: line-through;')
    for tag in spanTags:
        tag.clear()
    return tree


def __removeNonOclassTags(tree):
    '''
    Removes tags from a tree that are not relevant to the Object Class itself.

    Args:
        tree: An HTML tree.

    Returns:
        The same tree, without the label and other unrelated tags.
    '''
    tags = tree.findAll('a', {'class': 'footnoteref'})
    for tag in tags:
        tag.clear()
    tree = removeStrikethrough(tree)
    return tree


def verifyOclass(oclass):
    '''
    Checks if the input is a valid Object Class.

    Args:
        oclass: A str.

    Returns:
        True iff oclass is a valid Object Class.
    '''
    return oclass.lower() in constants.VALID_OBJECT_CLASSES


def handleAnomalousName(name, number):
    '''
    Handles number label and name formatting for special cases.

    Args:
        name: The name of the SCP, potentially including the label.
        number: The SCP's number.

    Returns:
        The proper format for the SCP's label and name.
    '''
    if number == '2565':
        return 'SCP-2565 - Allison Eckhart\n'
    return name + '\n'


class NoNameException(Exception):
    ''' Raised if no name is found for an SCP. '''
    pass


class NoOclassException(Exception):
    ''' Raised if no Object Class is found for an SCP. '''
    pass


class UnknownSeriesException(Exception):
    ''' Raised if the relevant series page can't be found for an SCP. '''
    pass
