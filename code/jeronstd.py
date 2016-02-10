#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging
import heapq
from messages import Upload, Request
from util import even_split
from peer import Peer
import itertools

class JERONStd(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        #np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        availability = [(0,0)] * self.conf.num_pieces
        for peer in peers:
            for piece_id in peer.available_pieces:
                if piece_id in needed_pieces:
                    availability[piece_id] = (availability[piece_id][0] + 1, piece_id)

        # create heap to keep track of most rare items, deleting empty elements (that the agent doesn't need)
        availability = [y for y in availability if y != (0,0)]
        #heapify a randomized availability list so that within each level of availability in the heap, elements are in random order
        random.shuffle(availability)
        heapq.heapify(availability)

        logging.debug("Availability: " + `availability`)


        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        #probably don't need this now
        #random.shuffle(needed_pieces)
        
        to_request = []
        count = 0
        while (len(availability) > 0 and count < self.max_requests * len(peers)):
            to_request.append(heapq.heappop(availability))
            count += 1
        logging.debug("To request: " + `to_request`)


        #compute ranked list of people I've contributed the most to from last 3 rounds (most likely to reciprocate/TfT)
        agents = {}
        for r in list(itertools.chain(*history.uploads[-3:])):
            if r.to_id in agents:
                agents[r.to_id] = agents[r.to_id] + r.bw
            else:
                agents[r.to_id] = r.bw

        logging.debug("Uploads: " + str(agents))


        peer_list = sorted(agents, key=agents.get)
        others = [y.id for y in peers if (y.id not in peer_list)]
        random.shuffle(others)
        peer_list += others
        peers.sort(key = lambda x : peer_list.index(x.id))
        logging.debug("Peer list: " + str(peer_list))
        logging.debug("Peers: " + str(peers))

        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            #get list of all pieces that we need that peer has in order of availability (rarest first)
            peer_request = [y for y in to_request if (y[1] in list(peer.available_pieces))]
            logging.debug("Pieces that peer " + peer.id + " has that I don't: " + str(peer_request))

            request_list = []
            if len(peer_request) == 0:
                continue

            if len(peer_request) == 1:
                start_block = self.pieces[peer_request[0][1]]
                r = Request(self.id, peer.id, peer_request[0][1], start_block)
                requests.append(r)
                continue

            level_list = [peer_request[0][1]]
            for i in range(1, len(peer_request)):
                if(peer_request[i][0]) == peer_request[i - 1][0] and i < len(peer_request) - 1:
                    logging.debug("same level, appending")
                    level_list.append(peer_request[i][1])
                else:
                    logging.debug("End of level " + `peer_request[i][0]` + " found")
                    if(peer_request[-1:][0] == peer_request[0][0]):
                        logging.debug("Only one level found, randomizing across it")
                        request_list = random.sample([y for (x,y) in peer_request], self.max_requests)
                        break
                    if len(level_list) + len(request_list) > self.max_requests:
                        logging.debug("this level would put it over the limit, randomizing")
                        request_list += random.sample(level_list, self.max_requests - len(request_list))
                        break
                    else:
                        logging.debug("This level doesn't fill up max requests, moving on to next level")
                        request_list += level_list
                        level_list = [peer_request[i][1]]
            logging.debug("Request list for peer " + peer.id + " = " + str(request_list))

            for piece_id in request_list:
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)
        logging.debug("Requests FINAL: " + str(requests))
        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            # change my internal state for no reason
            self.dummy_state["cake"] = "pie"

            request = random.choice(requests)
            chosen = [request.requester_id]
            # Evenly "split" my upload bandwidth among the one chosen requester
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
