# [<img src="https://raw.githubusercontent.com/dkempen/ha-efteling/master/custom_components/efteling/brand/icon.png" alt="" height="40" valign="top">][repository] Efteling for Home Assistant [<img src="https://raw.githubusercontent.com/dkempen/ha-efteling/master/custom_components/efteling/brand/logo.png" alt="" height="40" align="right">][efteling]

[![Home Assistant integration][home-assistant-badge]][home-assistant]
[![Marketplace install][marketplace-badge]][marketplace-install]
[![Latest release][version-badge]][version]
[![Validation][validation-badge]][validation]
[![License][license-badge]][license]
[![GitHub stars][stars-badge]][stars]

Bring Efteling's live attraction, show, and park information into Home Assistant with this integration. Build dashboards, receive notifications, and create automations around wait times, opening hours, shows, special events, and more to make the most of your visit to Efteling!

## Features

- **Attractions** - Live wait times, operating status, images, locations, and attraction details
- **Shows** - Current and upcoming show times, previous show times, status, and show information
- **Park information** - Park status, opening and closing times, and opening-hours schedules
- **Crowd levels** - Live crowd levels based on average attraction wait times, and crowd and occupancy forecasts
- **Events and maintenance** - Winter Efteling, business events, and planned attraction maintenance
- **Devices and entities** - Dedicated devices, custom icons, and data for dashboards and automations
- **Localization** - Dutch or English information, with translated entity names and states
- **Easy setup** - One-click installation and configuration through the Home Assistant UI

## Dashboard

The screenshot below shows an example of a dashboard built with this integration. You can also use the data in your own cards, scripts, notifications, and automations.

![Example Efteling Home Assistant dashboard](https://raw.githubusercontent.com/dkempen/ha-efteling/master/images/dashboard.jpg)

## Installation

### One-click installation

[![Add Efteling to Home Assistant][marketplace-install-badge]][marketplace-install]

### Manual installation

1. Open **Marketplace** in Home Assistant.
2. Select **Add from link**.
3. Paste the [repository URL][repository] into the GitHub link field.
4. Select **Integration** as the category.
5. Install **Efteling** and restart Home Assistant.

<details>
<summary>Manual installation without the Marketplace</summary>

1. Download the `custom_components/efteling/` directory from this repository.
2. Copy it into the `custom_components/` directory of your Home Assistant configuration.
3. Restart Home Assistant.

</details>

## Configuration

### One-click configuration

[![Open the Efteling config flow in Home Assistant][configure-badge]][configure]

### Manual configuration

The integration is configured through the Home Assistant UI. No account credentials or additional settings are required.

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Efteling**.
3. Select the language for information retrieved from Efteling: **Dutch** or **English**. Dutch is the default.
4. Complete the setup.

The integration creates three devices: **Efteling park**, **Efteling attractions**, and **Efteling shows**.

## Entities

### Park

The Efteling park device includes the following entities:

| Entity                        | Description                                                        |
| ----------------------------- | ------------------------------------------------------------------ |
| Park status                   | Whether the park is currently `Open` or `Closed`.                  |
| Attractions under maintenance | Number of attractions listed as being under maintenance today.     |
| Average wait time             | Average live wait time, in minutes, for open attractions.          |
| Crowd level                   | A level calculated from the average live wait time.                |
| Opening time                  | The park's opening time today.                                     |
| Closing time                  | The park's closing time today.                                     |
| Crowd forecast                | Efteling's crowd forecast for today: `Quiet`, `Normal`, or `Busy`. |
| Occupancy forecast            | Efteling's forecast park occupancy percentage for today.           |
| Business event                | Whether a business event is scheduled for today.                   |
| Winter Efteling               | Whether Winter Efteling is active today.                           |

Most entities expose additional attributes, including operating schedules, daily forecasts, event schedules, and upcoming maintenance information.

**Crowd forecast** and **crowd level** are different measurements. The forecast comes from Efteling's park information, while the integration calculates the crowd level from current attraction wait times. The average only includes attractions reported as open with a valid wait time.

### Attractions

Each attraction has a sensor whose value represents the current wait time in minutes. When an attraction is not open or no valid wait time is available, the sensor state is `unknown`.

For example:

```text
sensor.efteling_attractions_python
State: 20 min
```

Attraction sensors expose additional attributes for dashboards and automations:

| Attribute               | Description                      |
| ----------------------- | -------------------------------- |
| `status`                | Current attraction status.       |
| `empire`                | Efteling area or realm.          |
| `description`           | Attraction description.          |
| `subtitle`              | Attraction subtitle.             |
| `latitude`, `longitude` | Attraction coordinates.          |
| `image`, `image_detail` | Main and detail image URLs.      |
| `properties`            | Attraction properties.           |
| `entry_requirements`    | Entry requirements.              |
| `stimuli`               | Known sensory stimuli.           |
| `targetgroups`          | Target audiences.                |
| `type`                  | Efteling point-of-interest type. |

The attraction status is one of `Open`, `Closed`, `Under maintenance`, `Out of order`, or `Temporarily out of order`. Status labels follow the Home Assistant language setting.

### Shows

Each show has a timestamp sensor that provides the start time of the currently running show or, if no show is running, the next upcoming show. If no current or upcoming show is available, the sensor state is `unknown`.

For example:

```text
sensor.efteling_aquanura
State: 2026-10-21 21:00:00
```

Show sensors also expose the following attributes:

| Attribute               | Description                             |
| ----------------------- | --------------------------------------- |
| `status`                | Current show status.                    |
| `current_show_end`      | End time of the currently running show. |
| `previous_showtimes`    | Start times of previous shows.          |
| `upcoming_showtimes`    | Start times of upcoming shows.          |
| `duration_minutes`      | Show duration, in minutes.              |
| `edition`               | Show edition, when available.           |
| `empire`                | Efteling area or realm.                 |
| `description`           | Show description.                       |
| `subtitle`              | Show subtitle, when available.          |
| `latitude`, `longitude` | Show coordinates.                       |
| `image`, `image_detail` | Main and detail image URLs.             |
| `properties`            | Show properties.                        |
| `type`                  | Efteling point-of-interest type.        |

The show status is one of `Currently running`, `Upcoming`, or `No more shows today`. Status labels follow the Home Assistant language setting.

## Update intervals

| Data                                     | Refresh interval    | Examples                                                                      |
| ---------------------------------------- | ------------------- | ----------------------------------------------------------------------------- |
| Attraction wait times and show schedules | Every **5 minutes** | Wait times, show start and end times, and show status                         |
| Attraction and show metadata             | Every **24 hours**  | Names, descriptions, images, locations, and visitor information               |
| Park schedule information                | Every **24 hours**  | Opening hours, crowd and occupancy forecasts, events, and planned maintenance |

Time-sensitive entity states are also updated at relevant times, such as park opening and closing, local midnight, and show transitions, rather than relying solely on the next scheduled data refresh.

## Development

The integration's source code is located in `custom_components/efteling/`. You can use the Home Assistant development container to work on the integration. Run `scripts/setup` and `scripts/develop` to set up and launch a local Home Assistant environment.

## Credits

Efteling for Home Assistant is a community-developed custom integration that retrieves information published by Efteling. This project is independent and is not affiliated with or endorsed by Efteling.

Efteling and all associated trademarks, names, images, and services remain the property of their respective owners.

[repository]: https://github.com/dkempen/ha-efteling
[efteling]: https://www.efteling.com
[home-assistant]: https://www.home-assistant.io
[home-assistant-badge]: https://img.shields.io/badge/Home_Assistant-Integration-18bcf2.svg?logo=homeassistant&logoColor=white
[marketplace-badge]: https://img.shields.io/badge/Marketplace-Custom-18bcf2.svg?logo=HomeAssistantCommunityStore&logoColor=white
[version]: https://github.com/dkempen/ha-efteling/releases
[version-badge]: https://img.shields.io/github/v/release/dkempen/ha-efteling?label=Version
[stars]: https://github.com/dkempen/ha-efteling
[stars-badge]: https://img.shields.io/github/stars/dkempen/ha-efteling
[validation]: https://github.com/dkempen/ha-efteling/actions/workflows/hassfest.yaml
[validation-badge]: https://img.shields.io/github/actions/workflow/status/dkempen/ha-efteling/hassfest.yaml?logo=github&logoColor=fff&label=Validation
[license]: https://github.com/dkempen/ha-efteling?tab=MIT-1-ov-file
[license-badge]: https://img.shields.io/github/license/dkempen/ha-efteling?label=License
[marketplace-install]: https://my.home-assistant.io/redirect/marketplace_repository/?owner=dkempen&repository=ha-efteling&category=integration
[marketplace-install-badge]: https://my.home-assistant.io/badges/marketplace_repository.svg
[configure]: https://my.home-assistant.io/redirect/config_flow_start/?domain=efteling
[configure-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
