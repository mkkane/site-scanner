# from gevent import monkey
# monkey.patch_all()

from py2neo import neo4j, cypher, node, rel
from bs4 import BeautifulSoup
from celery import Celery
import requests
#import Queue
import urlparse
import logging

logger = logging.getLogger(__name__)
celery = Celery()
celery.config_from_object('celeryconfig')
db = neo4j.GraphDatabaseService("http://localhost:7474/db/data/")

SCHEME = 'http://'
SITE = 'www.test.com'

PAGE_INDEX_NAME = 'page'
PAGE_INDEX_KEY = 'url'
LINK_RELATIONSHIP_TYPE = 'LINKS_TO'

page_index = db.get_or_create_index(neo4j.Node, PAGE_INDEX_NAME)

@celery.task(name='scan.process_page')
def process_page(url):
    #url = node.get_properties()[PAGE_INDEX_KEY]
    node, = page_index.get(PAGE_INDEX_KEY, url)

    if been_processed(node):
        return

    logger.info('Retrieving Link: %s' % url)

    try:
        response = requests.head(SCHEME + url, allow_redirects=False)
        # TODO: allow_redirects and use response.history to create path in db
    except requests.RequestException as e:
        node.update_properties({ 
                'status': 'EXCEPTION',
                'content': repr(e)
                })
        return

    content_type = response.headers.get('content-type')

    node.update_properties({ 
            'status': response.status_code,
            'content-type': content_type
            })

    if not 'text/html' in content_type:
        return

    if not is_internal_path(url):
        logger.info('External Page: %s' % url)
        return

    # Get the full content
    try:
        response = requests.get(SCHEME + url, allow_redirects=False)
        # TODO: allow_redirects and use response.history to create path in db
    except requests.RequestException as e:
        return
    
    # We've got something, try to parse the response for any links
    soup = BeautifulSoup(response.content)
    a_tags = soup.find_all('a')

    for tag in a_tags:
        if tag.attrs.has_key('href'):
            process_link.delay(url, tag.attrs['href'])

@celery.task(name='scan.process_link')
def process_link(origin_node_url, link_path):
    '''Create a new node in the db for this path if we don't already
    know about it, and add it to the queue to be processed
    '''

    logger.info('Processing Link: %s' % link_path)
    origin_node, = page_index.get(PAGE_INDEX_KEY, origin_node_url)

    url = make_canonical_url(
        origin_node_url,#origin_node.get_properties()[PAGE_INDEX_KEY],
        link_path
        )

    # If we don't already have the target for this link in the db,
    # let's add it
    target_node = get_or_create_indexed_page_node(url)

    # Create the relationship if it doesn't exist
    path, = origin_node.get_or_create_path(LINK_RELATIONSHIP_TYPE, target_node)
    
    # If this node has previously been processed don't need to do
    # anything more)
    if been_processed(target_node):
        return

    # Add the new node to queue to be processed
    # queue.put(url)
    process_page.delay(url)

def been_processed(node):
    return node.get_properties().has_key('status')
    
def is_internal_path(url):
    full_url = SCHEME + url
    parsed_url = urlparse.urlparse(full_url)
    return parsed_url.netloc.lower() == SITE.lower()

def make_canonical_url(origin_url, link_path):
    joined = urlparse.urljoin(SCHEME + origin_url, link_path)
    parsed = urlparse.urlparse(joined)
    return parsed.netloc + parsed.path + parsed.query


def get_or_create_indexed_page_node(url):
    return db.get_or_create_indexed_node(
        PAGE_INDEX_NAME, 
        PAGE_INDEX_KEY, 
        url,
        properties={
            PAGE_INDEX_KEY : url
            })

# def push_initial_node():
#     root = get_or_create_indexed_page_node(SITE + '/')
    # queue.put(root.properties()[PAGE_INDEX_KEY])

# def process_queue():
#     while not queue.empty():
#         process_page(queue.get())

def run():
    base_url = SITE + '/'
    get_or_create_indexed_page_node(base_url)
    process_page.delay(base_url)
    #process_queue()


def logging_test():
    logger.debug('debug')
    logger.info('info')
    logger.warn('warn')
    logger.error('error')
