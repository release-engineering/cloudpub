# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 0.2.0 - 2023-08-09

- Do not filter out deprecated images on Azure

## 0.1.7 - 2023-08-01

- Bump internal dependencies

## 0.1.6 - 2023-06-28

- Bump `requests` to 2.31.0
- Azure: Fix publish to live
- Azure: reduce the wait interval for configure

## 0.1.5 - 2023-05-23

- Revert Azure: always overwrite images on draft
- Update the default schema version on Azure Session
- Fix typo in models.ms_azure.CorePricing

## 0.1.4 - 2023-05-10

- Azure: always overwrite images on draft

## 0.1.3 - 2023-03-30

- Fix Azure bug with deprecated Disk Versions

## 0.1.2 - 2023-03-23

AWS:
- Adds restricting versions

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
