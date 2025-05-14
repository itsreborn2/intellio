#!/bin/bash
sudo cp nginx/intellio.prod.conf /etc/nginx/sites-available/intellio.conf
sudo nginx -t
sudo systemctl restart nginx