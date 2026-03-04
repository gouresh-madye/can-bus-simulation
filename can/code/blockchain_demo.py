"""
Blockchain Proof-of-Concept for CAN Bus Verification

This module demonstrates why Blockchain is unsuitable for real-time
CAN bus intrusion detection due to computational overhead.

The implementation uses a simplified Proof-of-Work (PoW) blockchain
to "verify" CAN frames before processing - simulating a hypothetical
blockchain-based IDS.
"""

import hashlib
import time
import json


class Block:
    """
    Represents a single block in the blockchain.
    Each block contains CAN frame transactions that need verification.
    """
    
    def __init__(self, index, transactions, timestamp, previous_hash, nonce=0):
        self.index = index
        self.transactions = transactions  # CAN Frame Data
        self.timestamp = timestamp
        self.previous_hash = previous_hash
        self.nonce = nonce

    def compute_hash(self):
        """
        Compute SHA-256 hash of the block contents.
        This is the core cryptographic operation that makes blockchain secure
        but also computationally expensive.
        """
        block_string = json.dumps(self.__dict__, sort_keys=True, default=str)
        return hashlib.sha256(block_string.encode()).hexdigest()


class CANBlockchain:
    """
    A simplified blockchain implementation for CAN bus frame verification.
    
    In theory, this would ensure:
    - Message integrity (hash verification)
    - Message ordering (chain structure)
    - Attack resistance (proof-of-work)
    
    In practice, the computational overhead makes it unsuitable for
    real-time automotive applications.
    """
    
    def __init__(self, difficulty=2):
        """
        Initialize the blockchain.
        
        Args:
            difficulty: Number of leading zeros required in hash.
                       Higher = more secure but MUCH slower.
                       Bitcoin uses ~19, we use 2-4 for demonstration.
        """
        self.unconfirmed_transactions = []
        self.chain = []
        self.difficulty = difficulty
        self.create_genesis_block()
        
        # Statistics for analysis
        self.total_hashes_computed = 0
        self.mining_times = []

    def create_genesis_block(self):
        """Create the first block in the chain (no previous hash)."""
        genesis_block = Block(0, [], time.time(), "0")
        genesis_block.hash = genesis_block.compute_hash()
        self.chain.append(genesis_block)

    @property
    def last_block(self):
        """Get the most recent block in the chain."""
        return self.chain[-1]

    def add_new_transaction(self, can_frame):
        """
        Add a CAN frame to the pending transaction pool.
        
        In a blockchain-based IDS, every frame would need to be
        added here before it could be "trusted" and processed.
        
        Args:
            can_frame: Dictionary containing CAN frame data
                      (timestamp, id, dlc, data)
        """
        self.unconfirmed_transactions.append(can_frame)

    def proof_of_work(self, block):
        """
        The Proof-of-Work algorithm.
        
        This is the BOTTLENECK that makes blockchain unsuitable for CAN.
        
        It repeatedly computes hashes with different nonce values until
        a hash is found that starts with 'difficulty' zeros.
        
        For difficulty=2: ~256 hashes on average
        For difficulty=4: ~65,536 hashes on average
        For difficulty=6: ~16,777,216 hashes on average
        
        Each hash computation takes ~1-10 microseconds, but this adds up
        when CAN frames arrive every 0.5 milliseconds.
        """
        block.nonce = 0
        computed_hash = block.compute_hash()
        hashes_tried = 0
        
        while not computed_hash.startswith('0' * self.difficulty):
            block.nonce += 1
            computed_hash = block.compute_hash()
            hashes_tried += 1
            
        self.total_hashes_computed += hashes_tried
        return computed_hash

    def mine(self):
        """
        Mine a new block containing pending CAN frame transactions.
        
        This function:
        1. Creates a new block with all pending transactions
        2. Runs proof-of-work to find a valid hash
        3. Adds the block to the chain
        
        Returns:
            The mined block, or False if no transactions pending
        """
        if not self.unconfirmed_transactions:
            return False

        last_block = self.last_block

        new_block = Block(
            index=last_block.index + 1,
            transactions=self.unconfirmed_transactions.copy(),
            timestamp=time.time(),
            previous_hash=last_block.hash
        )

        # THIS IS THE BOTTLENECK - Proof of Work
        start_time = time.time()
        proof = self.proof_of_work(new_block)
        mining_time = time.time() - start_time
        self.mining_times.append(mining_time)
        
        # Block is now verified
        new_block.hash = proof
        self.chain.append(new_block)
        self.unconfirmed_transactions = []
        
        return new_block

    def get_statistics(self):
        """Return statistics about blockchain performance."""
        return {
            'total_blocks': len(self.chain),
            'total_hashes': self.total_hashes_computed,
            'avg_mining_time_ms': sum(self.mining_times) * 1000 / len(self.mining_times) if self.mining_times else 0,
            'total_mining_time_s': sum(self.mining_times),
            'difficulty': self.difficulty
        }


class LightweightMAC:
    """
    For comparison: A lightweight Message Authentication Code (MAC)
    implementation similar to what SecOC actually uses.
    
    This demonstrates the CORRECT approach for automotive security.
    """
    
    def __init__(self, secret_key="shared_secret_key"):
        self.secret_key = secret_key.encode()
    
    def compute_mac(self, can_frame):
        """
        Compute HMAC-SHA256 for a single CAN frame.
        
        This is what real automotive security (SecOC) uses:
        - Single hash computation (no proof-of-work loop)
        - Symmetric key (pre-shared, no consensus needed)
        - Constant time (~10 microseconds)
        """
        message = json.dumps(can_frame, sort_keys=True, default=str).encode()
        return hashlib.sha256(self.secret_key + message).hexdigest()[:16]
    
    def verify(self, can_frame, received_mac):
        """Verify a frame's MAC matches."""
        computed = self.compute_mac(can_frame)
        return computed == received_mac


if __name__ == "__main__":
    # Quick demonstration
    print("=== Blockchain vs Lightweight MAC Demo ===\n")
    
    # Sample CAN frame
    sample_frame = {
        "timestamp": 1234567890.123,
        "id": "0x316",
        "dlc": 8,
        "data": [0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0]
    }
    
    # Test Blockchain (difficulty 2)
    print("Testing Blockchain (difficulty=2)...")
    bc = CANBlockchain(difficulty=2)
    bc.add_new_transaction(sample_frame)
    
    start = time.time()
    bc.mine()
    bc_time = (time.time() - start) * 1000
    print(f"  Mining time: {bc_time:.2f} ms")
    print(f"  Hashes computed: {bc.total_hashes_computed}")
    
    # Test Lightweight MAC
    print("\nTesting Lightweight MAC (SecOC-style)...")
    mac = LightweightMAC()
    
    start = time.time()
    tag = mac.compute_mac(sample_frame)
    mac_time = (time.time() - start) * 1000
    print(f"  MAC computation time: {mac_time:.4f} ms")
    print(f"  MAC tag: {tag}")
    
    # Comparison
    print(f"\n=== Result ===")
    print(f"Blockchain is {bc_time/mac_time:.0f}x slower than SecOC")
    print(f"CAN frame interval: ~0.5 ms")
    print(f"Blockchain mining: {bc_time:.2f} ms")
    print(f"VERDICT: {'FAIL - Too slow' if bc_time > 0.5 else 'OK'}")
