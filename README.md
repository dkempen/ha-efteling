# [<img src="https://raw.githubusercontent.com/dkempen/ha-efteling/master/custom_components/efteling/brand/icon.png" alt="" height="40" valign="top">][repository] Efteling for Home Assistant [<img src="https://raw.githubusercontent.com/dkempen/ha-efteling/master/custom_components/efteling/brand/logo.png" alt="" height="40" align="right">][efteling]

[![Home Assistant integration][home-assistant-badge]][home-assistant]
[![Marketplace install][marketplace-badge]][marketplace-install]
[![Latest release][version-badge]][version]
[![License][license-badge]][license]
[![GitHub stars][stars-badge]][stars]

Bring Efteling's live attraction, show, and park information into Home Assistant with this Efteling integration. Use it to build dashboards, receive notifications, and create automations around wait times, opening hours, shows, special events, and more to make the most of your visit to Efteling!

## Features

- **Attractions** - Live wait times, operating status, descriptions, images, locations, and visitor information
- **Shows** - Current and upcoming show times, previous show times, status, and show information
- **Park information** - Opening and closing times, opening-hours schedule, crowd forecast, occupancy forecast, and average wait time
- **Crowd level** - A level calculated from the average live attraction wait time
- **Events and maintenance** - Winter Efteling, business events, and planned attraction maintenance
- **Home Assistant integration** - Dedicated devices, translated entity names and states, custom attraction and show icons, and data for dashboards and automations
- **Language selection** - Choose Dutch or English for information retrieved from Efteling

## Dashboard

The screenshot below shows one example of a dashboard built with the integration. The data can also be used in your own cards, scripts, notifications, and automations.

![Example Efteling Home Assistant dashboard](https://raw.githubusercontent.com/dkempen/ha-efteling/master/images/dashboard.jpg)

## Installation

### One-click installation

[![Add Efteling to Home Assistant][marketplace-install-badge]][marketplace-install]

### Manual installation

1. Open **Marketplace** in Home Assistant.
2. Select **Add from link**.
3. Paste the [repository URL][repository] into the GitHub link field.
4. Choose **Integration** as the category.
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
3. Select the language used for information retrieved from Efteling: **Dutch** or **English**. Dutch is the default.
4. Finish the setup.

The integration creates three devices: **Efteling park**, **Efteling attractions**, and **Efteling shows**.

## Entities

### Park

The Efteling park device includes these entities:

| Entity                     | Description                                                  |
| -------------------------- | ------------------------------------------------------------ |
| Park status                | Whether the park is currently `Open` or `Closed`             |
| Attractions in maintenance | Number of attractions listed as being in maintenance today.  |
| Average wait time          | Average live wait time for open attractions, in minutes.     |
| Crowd level                | A level calculated from the average live wait time.          |
| Opening time               | The park opening time today.                                 |
| Closing time               | The park closing time today.                                 |
| Crowd forecast             | Efteling's forecast for today: `Quiet`, `Normal`, or `Busy`. |
| Occupancy forecast         | Efteling's forecast park occupancy percentage for today.     |
| Business event             | Whether a business event is scheduled for today.             |
| Winter Efteling            | Whether Winter Efteling is active today.                     |

Relevant entities expose additional attributes such as operatring time schedules, daily forecasts, event schedules, and upcoming maintenance information.

**Crowd forecast** and **crowd level** are different measurements: the forecast comes from Efteling's park information, while crowd level is calculated by the integration from current attraction wait times. The average only includes attractions that are reported as open and have a valid wait time.

### Attractions

Each attraction has a sensor whose value is its current wait time in minutes. When the attraction is not open, or no valid wait time is available, the sensor state is `unknown`.

For example:

```text
sensor.efteling_attractions_python
State: 20 min
```

Attraction sensors expose additional information useful for dashboards and automations:

| Attribute               | Description                        |
| ----------------------- | ---------------------------------- |
| `status`                | Current attraction status.         |
| `empire`                | Efteling area or realm.            |
| `description`           | Attraction description.            |
| `subtitle`              | Attraction subtitle.               |
| `latitude`, `longitude` | Attraction coordinates.            |
| `image`, `image_detail` | Main and detail image URLs.        |
| `properties`            | Attraction properties.             |
| `entry_requirements`    | Entry requirements.                |
| `stimuli`               | Known sensory stimuli information. |
| `targetgroups`          | Target audiences.                  |
| `type`                  | Efteling point-of-interest type.   |

The attraction status is one of `Open`, `Closed`, `In maintenance`, `Out of order`, or `Temporarily out of order` (shown in the Home Assistant language).

### Shows

Each show has a timestamp sensor. Its value is the start time of the currently running show, or the next upcoming show when none is running. If there is no current or upcoming show, the state is `unknown`.

Show sensors expose attributes for the show status, end time of the current show, previous and upcoming show times, duration, edition, location, description, images, and other show information. Show status is one of `Currently running`, `Upcoming`, or `No more shows today`.

### Shows

Each show has a timestamp sensor containing the start time of the currently running show, or the next upcoming show when no show is currently running. When no current or upcoming show is available, the sensor state is `unknown`.

For example:

```text
sensor.efteling_aquanura
State: 2026-10-21 21:00:00
```

Show sensors also expose additional attributes:

| Attribute               | Description                             |
| ----------------------- | --------------------------------------- |
| `status`                | Current show status.                    |
| `current_show_end`      | End time of the currently running show. |
| `previous_showtimes`    | Start times of previous shows.          |
| `upcoming_showtimes`    | Start times of upcoming shows.          |
| `duration_minutes`      | Duration of the show, in minutes.       |
| `edition`               | Show edition, when available.           |
| `empire`                | Efteling area or realm.                 |
| `description`           | Show description.                       |
| `subtitle`              | Show subtitle, when available.          |
| `latitude`, `longitude` | Show coordinates.                       |
| `image`, `image_detail` | Main and detail image URLs.             |
| `properties`            | Show properties.                        |
| `type`                  | Efteling point-of-interest type.        |

The show status is one of `Currently running`, `Upcoming`, or `No more shows today` (shown in the Home Assistant language).

## Update intervals

| Data                                     | Refresh interval    | Examples                                                                      |
| ---------------------------------------- | ------------------- | ----------------------------------------------------------------------------- |
| Attraction wait times and show schedules | Every **5 minutes** | Wait times, show start/end information, and show status                       |
| Attraction and show metadata             | Every **24 hours**  | Names, descriptions, images, locations, and visitor information               |
| Park schedule information                | Every **24 hours**  | Opening hours, crowd and occupancy forecasts, events, and planned maintenance |

Time-sensitive entity states are also updated at relevant boundaries, such as park opening/closing times, local midnight, and show transitions, rather than relying only on the next data refresh.

## Development

The integration source is in `custom_components/efteling/`. Development can be done using the Home Assistant development container; use `scripts/setup` and `scripts/develop` to set up and run a local Home Assistant environment.

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
[license]: https://github.com/dkempen/ha-efteling?tab=MIT-1-ov-file
[license-badge]: https://img.shields.io/github/license/dkempen/ha-efteling?label=License
[marketplace-install]: https://my.home-assistant.io/redirect/marketplace_repository/?owner=dkempen&repository=ha-efteling&category=integration
[marketplace-install-badge]: https://my.home-assistant.io/badges/marketplace_repository.svg
[configure]: https://my.home-assistant.io/redirect/config_flow_start/?domain=efteling
[configure-badge]: https://my.home-assistant.io/badges/config_flow_start.svg
