CURRENT_DIR :=$(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
DST_DIR := ./
SRC_DIR := $(CURRENT_DIR)
grpcio-tools:
	pip3 install "grpcio-tools>=1.0.0"
	pip3 install "protobuf>=3.0.0"

protos: grpcio-tools *.proto
	@echo "Generating python code for .proto files"
	python3 $(SRC_DIR)/gen_protos.py $(SRC_DIR) $(SRC_DIR) $(DST_DIR)
