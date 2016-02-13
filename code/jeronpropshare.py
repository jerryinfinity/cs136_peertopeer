#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers 
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

import itertools

class JERONPropShare(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"

        # ratio of bandwidth allocated to optimistic unchoking to total upload bw available
        self.OPT_UNCHOKE_RATIO = 0.10 



    
    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)
        
        # Sort peers by id.  This is probably not a useful sort, but other 
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(isect, n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

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

            # modified this from JERONStd
            # who uploads to me last round and by how much?
            # agents contains those uploaded to me last round
            # this list explosion with [-1:] prevents bugs when history.downloads is empty
            agents = {}
            for r in list(itertools.chain(*history.downloads[-1:])):
                if r.from_id in agents:
                    agents[r.from_id] = agents[r.from_id] + r.blocks
                else:
                    agents[r.from_id] = r.blocks

            

            total_blocks_received = sum(agents.values())

            requests_id = [request.requester_id for request in requests]

            # id of peers that upload to this agent last round and request me this round
            # they will get proportional shares
            
            prop_peers = [r_id for r_id in agents.keys() if r_id in requests_id]

            # peers that request to me this round but did not give me last round
            # one of them will be optimistically unchoked
            optimistic_peers = [r_id for r_id in requests_id if r_id not in prop_peers]

            # now build chosen and bws
            chosen = []
            bws = []

            # peer_bw_pair = []
            for p in prop_peers:
                chosen += [p]
                bws += [int(agents[p]*self.up_bw*(1-self.OPT_UNCHOKE_RATIO)/total_blocks_received)]

            # random.choice gives error if the input sequence is empty, hence this
            if len(optimistic_peers)>0:
                lucky_peer_id = random.choice(optimistic_peers)
                chosen += [lucky_peer_id]
                bws += [int(self.OPT_UNCHOKE_RATIO*self.up_bw)]


        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]
            
        return uploads
