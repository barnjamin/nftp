#!/bin/bash

ps -fu ben | grep 'python main.py' | grep -v 'grep' | awk '{print $2}' | xargs kill 