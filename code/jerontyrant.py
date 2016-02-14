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
import sys

class JERONTyrant(Peer):
  

    def post_init(self):
        print "post_init(): %s here!" % self.id

        self.NUM_SLOTS = 4

        # constants, Piatek et al (2007)
        self.ALPHA = 0.2
        self.GAMMA = 0.1

        # how many periods earlier each peer j unchokes me 
        self.unchoke_me_count = dict()

        # estimate d_j, download rate, and u_j, upload rate, for each neighbor j 

        # estimates of d_j, the current download rate that j provides its unchoked peers
        # if I am currently unchoked by j, d_j is the actual download bandwidth
        # otherwise I estimate d_j. 
        self.download_rates = dict()
        # estimates of u_j, the upload rate a peer must allocate to peer j to become 
        # unchoked at j
        self.upload_rates = dict()
      


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




        if history.current_round() == 0:
            
            for p in peers:
                self.unchoke_me_count[p.id] = 0

        else:

            # need to put here because if first round, history.downloads is empty
            # and you will get index out of bound error

            # peers j that I upload to and j downloads to this agent 

            # no longer needed
            # most_recent_downloads = history.downloads[len(history.downloads)-1]

            # dict from_id: total number of blocks downloaded last round

            # peers_unchoke_me = [download.from_id for download in most_recent_downloads]

            peers_unchoke_me = []
            for r in list(itertools.chain(*history.downloads[-1:])):
                peers_unchoke_me += [r.from_id]

            for p in peers:
                # if p unchokes me last period
                if p in peers_unchoke_me:
                    self.unchoke_me_count[p.id] += 1
                else:
                    self.unchoke_me_count[p.id] = 0


            # START estimating d_j and u_j

            for r in list(itertools.chain(*history.downloads[-1:])):
                if r.from_id in self.download_rates:
                    self.download_rates[r.from_id] = self.download_rates[r.from_id] + r.blocks
                else:
                    self.download_rates[r.from_id] = r.blocks

            for p in peers:
                # for peers that don't unchoke me, use stale estimate from
                # block announcement rate
                # for peer j, if b pieces are available, r rounds so far, then
                # peer j's download rate is b*blocks_per_piece/r
                # assume that for peer j, upload rate and download rate are equal,
                # so this is an estimate for d_j
                if p not in peers_unchoke_me:
                    self.download_rates[p.id] = len(p.available_pieces)*self.conf.blocks_per_piece/history.current_round()


 

        # Now, estimate u_j upload_rates
        # if first round (current_round==0) initialize with equal split capacities
        # if not first round, 

        if history.current_round() == 0:
            for p in peers:
                self.upload_rates[p.id] = self.up_bw / self.NUM_SLOTS
        else:

            for p in peers:
                # if peer p unchokes this agent for the last 3 periods
                # 3 periods - constant from Piatek et al
                if self.unchoke_me_count[p.id] >= 3:
                    self.upload_rates[p.id] *= (1-self.GAMMA) 
                if p not in peers_unchoke_me:
                    self.upload_rates[p.id] *= (1+self.ALPHA) 

        # END estimating d_j and u_j

        # NOW start processing the request

        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            # it used to be called "chosen" This name is more descriptive
            peers_to_unchoke = []
            bws = []
        else:
            requests_id = [request.requester_id for request in requests]
            # use list, because we want to sort by d_j/u_j
            # each element in list is (peer_id, d_j, u_j)
            triples = []
            for r_id in requests_id:
                triples += [(r_id, self.download_rates[r_id], self.upload_rates[r_id])]



            # sort by d_j/u_j in descending order
            triples = sorted(triples, key=lambda x: 1.*x[1]/x[2] if x[2]!=0 else sys.float_info.max, reverse=True)

            peers_to_unchoke = []

            sum_of_u = 0

            # This can be determined dynamically, but here we will just fix it
            cap = self.up_bw


            # keep adding peers to unchoke until sum of u-s exceed cap
            for triple in triples:
                sum_of_u += triple[2]
                if sum_of_u <= cap:
                    peers_to_unchoke += [triple[0]]


            # Evenly "split" my upload bandwidth among the one chosen requester
            if len(peers_to_unchoke) > 0:
                bws = even_split(self.up_bw, len(peers_to_unchoke))
            else:
                bws = []

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(peers_to_unchoke, bws)]
            
        return uploads
