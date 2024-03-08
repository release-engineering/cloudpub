# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 0.7.0 - 2024-03-08

- Pin the Azure schema for VMIPlanTechConfig

## 0.6.1 - 2024-02-27

- AWS: Adds access endpoint url

## 0.6.0 - 2024-02-27

- Azure: add property security_type to VMISku
- Log unused JSON attributes during class conversion
- AWS: Allows access to timeout attempts through AWSProductService

## 0.5.1 - 2024-02-13

- Azure: Include SV in SAS comparison exclusion
- Remove JSON conversion debug logs

## 0.5.0 - 2024-01-XX

- Azure: Check first for draft instead live
- Azure: Force submitting offer to "preview" when it's on "stage to preview" mode
- Azure: Reduce pooling interval

## 0.4.2 - 2023-11-08

- Azure: Fix the `Audience` constructor for `ProductReseller``
- Bump urllib3 to `1.26.18` to fix a CVE

## 0.4.1 - 2023-10-20

- Azure: Fix validator for VMImageSource
- Azure: No longer filter out deprecated images

## 0.4.0 - 2023-10-04

- Azure: allow publishing to `preview`
- AWS: Add AMI Ids to RestrictVersion return to allow deleting images/snapshots

## 0.3.2 - 2023-09-14

- Azure: Do not fail on 50X errors from job status

## 0.3.1 - 2023-09-12

- Fix bug when dealing with scheduled deprecation images on Azure.

## 0.3.0 - 2023-09-06

- Use AWS models to validate and manipulate the boto3 requests/responses
- Enhance the `is_sas_eq` logs for Azure to better distinct the expected and received SAS URI

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
