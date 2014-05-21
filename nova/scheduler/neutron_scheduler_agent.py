__author__ = 'nalle'

from oslo import messaging
from nova.openstack.common import jsonutils
from nova import rpc
import copy
from nova.objects import base as objects_base
import pika
import kombu


class NeutronScheduler(object):
    def __init__(self, topic):
        super(NeutronScheduler, self).__init__()
        self.topic = topic
        target = messaging.Target(topic=self.topic, version='1.0')
        serializer = objects_base.NovaObjectSerializer()
        self.client = rpc.get_client(target, serializer=serializer)
        self.host_dict = []
      #  pika_con()
        kombu_con()

    def neutron_scheduler(self, hosts, chain_name, weights, instance, **kwargs):
        """Make a remote process call to use Neutron's filter scheduler."""
        client = self.client.prepare()
        context = instance.pop('context')
        new_hosts = copy.deepcopy(hosts)

        for i in new_hosts:
            i.__dict__.pop('updated')
            i.__dict__.pop('service')
            self.host_dict.append(i.__dict__)

        return client.call(context, 'neutron_filter_scheduler',
                           instance=jsonutils.to_primitive(instance),
                           hosts=jsonutils.to_primitive(self.host_dict),
                           chain_name=chain_name,
                           weight_functions=weights,
                           **kwargs)


def pika_con():

    credentials = pika.PlainCredentials('guest', 'simple')
    parameters = pika.ConnectionParameters('localhost',
                                       5672,
                                       '/',
                                       credentials)

    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_bind(exchange='nova',
                       queue='topic.filter_scheduler',
                       routing_key='topic.filter_scheduler')


def kombu_con():
    conn = kombu.Connection('amqp://guest:simple@localhost:5672//')
    channel = conn.channel()
    queue = kombu.Queue('topic.filter_scheduler')
    bound_queue = queue(channel)
    bound_queue.bind_to(exchange='nova', routing_key='topic.filter_scheduler')