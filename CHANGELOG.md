# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 0.1.1 - 2023-03-21

Azure:

- Change disk version to be mandatory
- Refactor the `publish` method
- Fix bad converter for Government Certification
- Fix the friendly_name on OSDetails for Azure
- Fix code smells

AWS:

- Fix timeout security issue
- Update timeout attempts/ intervals

## 0.1.0 - 2023-02-22

This is the first version of `cloudpub`, capable of:

- Associating and publishing a VHD image on Azure through the Product Ingestion API.
- Associating and publishing an AMI on AWS through Boto3.
