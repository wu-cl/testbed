#!/usr/bin/env python2

# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.util import dumpNetConnections
from p4_mininet import P4Switch, P4Host

import argparse
from time import sleep

parser = argparse.ArgumentParser(description='Mininet demo')
parser.add_argument('--behavioral-exe', help='Path to behavioral executable',
                    type=str, action="store", required=True)
parser.add_argument('--thrift-port', help='Thrift server port for table updates',
                    type=int, action="store", default=9090)
parser.add_argument('--num-hosts', help='Number of hosts to connect to switch',
                    type=int, action="store", default=2)
parser.add_argument('--mode', choices=['l2', 'l3'], type=str, default='l3')
parser.add_argument('--json', help='Path to JSON config file',
                    type=str, action="store", required=True)
parser.add_argument('--pcap-dump', help='Dump packets on interfaces to pcap files',
                    type=str, action="store", required=False, default=False)

args = parser.parse_args()

class DemoSwitch(P4Switch):
    """ Demo switch that can hot-swap one query JSON for another. """
    def __init__(self, 
                 name, 
                 sw_path = None, 
                 json_path = None, 
                 thrift_port = None, 
                 pcap_dump = None, 
                 **kwargs):
        P4Switch.__init__(self, name,
                          sw_path = sw_path,
                          json_path = json_path,
                          thrift_port = thrift_port,
                          pcap_dump = pcap_dump,
                          **kwargs)

    def restart(self, json_path):
        """Restart a new P4 switch with the new JSON"""
        print "Stopping P4 switch", self.name
        """ Execute part of the stop() routine. """
        self.output.flush()
        self.cmd('kill %' + self.sw_path)
        self.cmd('wait')
        """ Now re-run part of the start() routine that constructs a new switch
        path with the new JSON argument. """
        self.json_path = json_path
        args = [self.sw_path]
        # args.extend( ['--name', self.name] )
        # args.extend( ['--dpid', self.dpid] )
        for port, intf in self.intfs.items():
            if not intf.IP():
                args.extend( ['-i', str(port) + "@" + intf.name] )
        if self.pcap_dump:
            args.append("--pcap")
            # args.append("--useFiles")
        if self.thrift_port:
            args.extend( ['--thrift-port', str(self.thrift_port)] )
        if self.nanomsg:
            args.extend( ['--nanolog', self.nanomsg] )
        args.extend( ['--device-id', str(self.device_id)] )
        # P4Switch.device_id += 1
        args.append(self.json_path)
        if self.enable_debugger:
            args.append("--debugger")
        logfile = '/tmp/p4s.%s.log' % self.name
        print ' '.join(args)

        self.cmd( ' '.join(args) + ' >' + logfile + ' 2>&1 &' )
        # self.cmd( ' '.join(args) + ' > /dev/null 2>&1 &' )

        print "switch has been restarted"

class SingleSwitchTopo(Topo):
    "Single switch connected to n (< 256) hosts."
    def __init__(self, sw_path, json_path, thrift_port, pcap_dump, n, **opts):
        # Initialize topology and default options
        Topo.__init__(self, **opts)

        switch = self.addSwitch('s1',
                                sw_path = sw_path,
                                json_path = json_path,
                                thrift_port = thrift_port,
                                pcap_dump = pcap_dump)
        
        for h in xrange(n):
            host = self.addHost('h%d' % (h + 1),
                                ip = "10.0.%d.10/24" % h,
                                mac = '00:04:00:00:00:%02x' %h)
            self.addLink(host, switch)

def main():
    num_hosts = args.num_hosts
    mode = args.mode

    topo = SingleSwitchTopo(args.behavioral_exe,
                            args.json,
                            args.thrift_port,
                            args.pcap_dump,
                            num_hosts)
    net = Mininet(topo = topo,
                  host = P4Host,
                  switch = DemoSwitch,
                  controller = None)
    net.start()


    sw_mac = ["00:aa:bb:00:00:%02x" % n for n in xrange(num_hosts)]

    sw_addr = ["10.0.%d.1" % n for n in xrange(num_hosts)]

    for n in xrange(num_hosts):
        h = net.get('h%d' % (n + 1))
        if mode == "l2":
            h.setDefaultRoute("dev eth0")
        else:
            h.setARP(sw_addr[n], sw_mac[n])
            h.setDefaultRoute("dev eth0 via %s" % sw_addr[n])
    s1 = net.get('s1')
    print 's1-eth1 IP = %s' % s1.intf('s1-eth1').IP()
    print 's1-eth2 IP = %s' % s1.intf('s1-eth2').IP()
    for n in xrange(num_hosts):
        h = net.get('h%d' % (n + 1))
        h.describe()

    sleep(1)
    dumpNetConnections(net)
    print "Ready !"

    CLI( net )
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    main()
