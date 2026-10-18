# [<img src="custom_components/efteling/brand/icon.png" alt="" height="40" valign="top">][repository] Efteling for Home Assistant [<img src="custom_components/efteling/brand/logo.png" alt="" height="40" align="right">][efteling]

[![Marketplace][home-assistant-badge]][home-assistant]
[![Marketplace][marketplace-badge]][marketplace-install]
[![Version][version-badge]][version]
[![License][license-badge]][license]
[![Stars][stars-badge]][stars]

A Home Assistant integration that brings real-time Efteling attraction and show information into Home Assistant.

This integration retrieves data from the Efteling and exposes attractions and shows as Home Assistant sensor entities, making it possible to build dashboards, notifications, automations, and other Home Assistant functionality around your visit to Efteling.

## Features

- Attraction wait times
- Attraction operating status
- Show times: previous, current and upcoming
- Attraction and show information, locations and images
- Custom icons for attractions and shows
- Simple one-click install
- Ready for dashboarding and automations
- Even more features coming _Soon™_

## Installation

### One-click installation

[![Open your Home Assistant instance and open this repository inside the Marketplace.][marketplace-install-badge]][marketplace-install]

### Manual installation

This integration can be installed as a custom repository in the Home Assistant Marketplace.

In Home Assistant:

1. Open **Marketplace**.
2. Select **Add from link**.
3. Paste the [url of this repository][repository] in the GitHub link field.
4. Select **Integration** as the category.
5. Install **Efteling**.
6. Restart Home Assistant.

<details>
<summary>Really manual Installation</summary>

1. Download the `custom_components/efteling/` folder from this repository
2. Copy it to your Home Assistant's `custom_components/` directory
3. Restart Home Assistant

</details>

## Configuration

### One-click configuration

[![Open your Home Assistant instance and configure this integration.][configure-badge]][configure]

### Manual configuration

The integration is configured entirely through the Home Assistant UI.

1. Go to: **Settings → Devices & services → Add integration**
2. Search for: **Efteling**
3. Optionally set the language of the ride and show details. No other configuration is required.
4. Done! Efteling is in your Home Assistant!

## Roadmap

Features coming _Soon™_:

- [x] Attraction wait time
- [x] Attraction status
- [x] Attraction information
- [x] Show times
- [x] Show status
- [x] Show information
- [ ] Crowd level forecast
- [ ] Annual pass validity
- [ ] Opening times
- [ ] Special events
- [ ] Stable v1 release

## Entities

The integration currently provides attractions and shows information.

### Attractions

Each supported attraction is represented by a sensor with a duration value in minutes.

For an open attraction, the sensor state contains the current waiting time.

For example:

```text
sensor.efteling_attracties_python
State: 20 min
```

When an attraction is not open or no wait time is available, the sensor state is `unknown`/`None`.

Attraction sensors also expose additional attributes:

| Attribute            | Description               |
| -------------------- | ------------------------- |
| `empire`             | Efteling area/realm       |
| `status`             | Current attraction status |
| `description`        | Attraction description    |
| `subtitle`           | Attraction subtitle       |
| `latitude`           | Attraction latitude       |
| `longitude`          | Attraction longitude      |
| `image`              | Main image                |
| `image_detail`       | Detail image              |
| `properties`         | Attraction properties     |
| `entry_requirements` | Entry requirements        |
| `stimuli`            | Known stimuli information |
| `targetgroups`       | Target audiences          |
| `type`               | Efteling POI type         |

The attraction status can be one of the following values:

| Attraction status          |
| -------------------------- |
| `Open`                     |
| `Closed`                   |
| `In maintenance`           |
| `Out of order`             |
| `Temporarily out of order` |

### Shows

Each supported show is represented by a timestamp sensor.

The sensor state contains:

- The start time of the currently running show, or
- The next upcoming show when no show is currently running.

For example:

```text
sensor.efteling_aquanura
State: 2026-09-06 21:00:00
```

Show sensors also expose additional attributes:

| Attribute            | Description                    |
| -------------------- | ------------------------------ |
| `status`             | Current show status            |
| `current_show_start` | Start time of the current show |
| `current_show_end`   | End time of the current show   |
| `previous_showtimes` | Previous show start times      |
| `upcoming_showtimes` | Upcoming show start times      |
| `duration_minutes`   | Show duration                  |
| `edition`            | Show edition                   |
| `empire`             | Efteling area/realm            |
| `description`        | Show description               |
| `subtitle`           | Show subtitle                  |
| `latitude`           | Show latitude                  |
| `longitude`          | Show longitude                 |
| `image`              | Main image                     |
| `image_detail`       | Detail image                   |
| `properties`         | Show properties                |
| `type`               | Efteling POI type              |

The show status can be one of the following values:

| Show status           |
| --------------------- |
| `Currently running`   |
| `Upcoming`            |
| `No more shows today` |

## Update intervals

The integration uses two independent data sources.

### Attraction and show data

Wait time and show information is refreshed every **5 minutes**.

### Metadata information

Attraction and show metadata is refreshed every **24 hours**.

## Devices

The integration groups its entities into two Home Assistant devices:

### Efteling attracties

Contains all attraction sensors.

### Efteling shows

Contains all show sensors.

## Dashboard example

A simple dashboard can display attraction queues alongside show times.

## Automations

The sensors or their attributes directly in Home Assistant automations.

- Notify when an attraction's wait time drops below a threshold.
- Notify when an attraction reopens after being out of order.
- Receive a reminder shortly before a show starts.

## Development

The integration can be developed and tested using a Home Assistant development container.

The integration source lives under `custom_components/efteling`.

The main components are:

| File             | Purpose                                             |
| ---------------- | --------------------------------------------------- |
| `__init__.py`    | Integration setup, coordinators, and platform setup |
| `api.py`         | Efteling API client                                 |
| `config_flow.py` | UI-based configuration flow                         |
| `const.py`       | Integration constants and custom icons              |
| `coordinator.py` | Home Assistant data update coordinators             |
| `data.py`        | Runtime data structures                             |
| `models.py`      | API response models                                 |
| `sensor.py`      | Attraction and show entities                        |
| `manifest.json`  | Home Assistant integration metadata                 |

## Credits

This is a non-commercial, community-developed custom integration for Home Assistant that provides data from Efteling.

Efteling and all associated trademarks, names, images, and services remain the property of their respective owners.
This project is independent and is not affiliated with or endorsed by Efteling.

[repository]: https://github.com/dkempen/ha-efteling
[efteling]: https://www.efteling.com
[home-assistant]: https://www.home-assistant.io
[home-assistant-badge]: https://img.shields.io/badge/Home_Assistant-Integration-18bcf2.svg?logo=homeassistant&logoColor=white
[marketplace-badge]: https://img.shields.io/badge/Marketplace-Custom-18bcf2.svg?logo=HomeAssistantCommunityStore&logoColor=white
[version]: https://github.com/dkempen/ha-efteling/releases
[version-badge]: https://img.shields.io/github/v/release/dkempen/ha-efteling?label=Version
[stars]: https://github.com/dkempen/ha-efteling
[stars-badge]: https://img.shields.io/github/stars/dkempen/ha-efteling
[license]: https://github.com/dkempen/ha-efteling?tab=MIT-1-ov-file
[license-badge]: https://img.shields.io/github/license/dkempen/ha-efteling
[marketplace-install]: https://my.home-assistant.io/redirect/marketplace_repository/?owner=dkempen&repository=ha-efteling&category=integration
[marketplace-install-badge]: https://my.home-assistant.io/badges/marketplace_repository.svg
[configure]: https://my.home-assistant.io/redirect/config_flow_start/?domain=efteling
[configure-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
