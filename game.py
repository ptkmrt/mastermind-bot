"""
Class for mastermind game instance
Secret 4-dot pattern is randomly generated from red, blue, green, yellow, white, orange
User has X amount of guesses, each of which (except the last) is replied to with a clue
All previous guesses and matching clues are displayed in an increasing, stacked format
"""
from collections import Counter
import random
import re

CODE_LEN = 4
MAX_GUESSES = 8

class Game:
    """Instance of one game of mastermind"""
    def __init__(self, code=None):
        self.guesses = []  # everything the player has guessed
        self.clueboard = []  # clues shown after each guess (red & white squares)
        
        if code is None:
            self.generate_code()
        else:
            self.code = code
        self.dot_nums = Counter(self.code)  # color counts
        print(f"The secret pattern is {self.code}")  # sanity check
        
        self.code_len = CODE_LEN  # default 4
        self.max_guesses = MAX_GUESSES  # default 8
    
    def generate_code(self):
        """Creates a random 4dot sequence"""
        code = ""
        for _ in range(4):
            num = random.randint(0, 70)
            if num < 10:
                code += "🔴"
            elif num < 20:
                code += "🟠"
            elif num < 40:
                code += "🟡"
            elif num < 50:
                code += "🟢"
            elif num < 60:
                code += "🔵"
            else:
                code += "🟣"

        self.code = code


    def add_guess(self, guess):
        counts = self.dot_nums.copy()
        pegs = ""

        if guess == self.code:  # correct
            return 0
        if not self.valid_pattern(guess):  # invalid
            return -1
        if len(self.guesses) + 1 == self.max_guesses:  # incorrect, no tries left
            return -2

        # check for correct color, correct spot
        for i in range(CODE_LEN):
            dot = guess[i]
            if dot == self.code[i]:
                pegs += "◼"
                counts[dot] -= 1
        
        # check for correct color, wrong spot
        for i in range(CODE_LEN):
            dot = guess[i]
            if (dot != self.code[i] and guess[i] in self.code and counts[dot] > 0): 
                pegs += "◻"
                counts[dot] -= 1    
        
        # randomize order
        chars = list(pegs)
        random.shuffle(chars)
        clue = ''.join(chars)

        self.guesses.append(guess)
        self.clueboard.append(clue)
        return clue


    def display_board(self):
        display = ""
        for i, clue in enumerate(self.clueboard, start=1):
            display += str(i) + ":  " + clue + "  ||  " + self.guesses[i-1] + "\n"
        return display


    def valid_pattern(self, pattern):
        dots = ["🟣", "🔴", "🟠", "🟡", "🟢", "🔵"]
        regex = f"^({'|'.join(re.escape(d) for d in dots)}){{{CODE_LEN}}}$"
        return bool(re.match(regex, pattern))