# Library Management System

## Table of Contents

- [Library Management System](#library-management-system)
  - [Table of Contents](#table-of-contents)
    - [Introduction](#introduction)
    - [First Block: Basic Library Management](#first-block-basic-library-management)
      - [1. Library Catalog Management](#1-library-catalog-management)
        - [Design and Implementation](#design-and-implementation)
        - [Result and Next Steps](#result-and-next-steps)
        - [Acceptance Criteria](#acceptance-criteria)
        - [Tasks](#tasks)
        - [Conclusion](#conclusion)
      - [2. Viewing Book Cover and Synopsis](#2-viewing-book-cover-and-synopsis)
        - [Design and Implementation](#design-and-implementation-1)
        - [Result and Next Steps](#result-and-next-steps-1)
        - [Acceptance Criteria](#acceptance-criteria-1)
        - [Tasks](#tasks-1)
        - [Conclusion](#conclusion-1)
      - [3. Locating Books in the Library](#3-locating-books-in-the-library)
        - [Design and Implementation](#design-and-implementation-2)
        - [Result and Next Steps](#result-and-next-steps-2)
        - [Acceptance Criteria](#acceptance-criteria-2)
        - [Tasks](#tasks-2)
        - [Conclusion](#conclusion-2)
    - [Development Process for User Stories 1-3](#development-process-for-user-stories-1-3)
    - [Note on Future Development](#note-on-future-development)
    - [Appendix: Technical Specifications](#appendix-technical-specifications)
    - [Summary](#summary)

### Introduction

The Library Management System project is conceived as a robust platform that aims to revolutionize the way libraries manage their catalog and interact with their users. At the core of its design lies the aspiration to bridge traditional library management with modern technology, providing intuitive access to books, user accounts, reviews, and more. The original idea emerged from the need to make library resources more accessible and engaging, fueling a lifelong love for reading. The decision to embrace the Agile methodology was strategic, allowing the development team to be responsive to changes, foster collaboration, and iteratively build features that align closely with user needs and expectations. Agile's flexible and adaptive approach promotes a user-centered design and ensures that the system evolves with ongoing feedback and real-world testing.

### First Block: Basic Library Management

#### 1. Library Catalog Management

As a librarian, I can have a database to add, delete, and modify book information, so that the catalog stays up to date.

##### Design and Implementation

The traditional CRUD methodology was adopted in a simplified form. Django's built-in `/admin` tool provides a user-friendly interface for the librarian's needs. For details on the database schema, refer to [Appendix: Technical Specifications](#appendix-technical-specifications).

##### Result and Next Steps

The outcome of this stage serves as a minimum viable product (MVP) in the Agile process. Looking ahead, future iterations will leverage more sophisticated databases, automating the process of managing the library catalog.

##### Acceptance Criteria

- The librarian can add, delete, and modify the information of books in the database. ✅

##### Tasks

- Create a superuser using Django.
- Use Django's admin tools to add, modify, and delete books.

##### Conclusion

This stage successfully establishes a foundational layer for managing the library database, reflecting a critical first step in the Agile journey.

#### 2. Viewing Book Cover and Synopsis

**As a user, I can view the book cover and read a synopsis, so that I can determine if I'm interested in it.**

##### Design and Implementation

The traditional CRUD methodology was considered but not fully adopted, as users neither need nor have permission to modify the books database. The Read function was the only method applied.

##### Result and Next Steps

The books in the library are displayed on an HTML page, accessible to everyone. Future developments will allow more user-friendly access to the books and improved design.

##### Acceptance Criteria

- Users can see an HTML version of all books, including a synopsis and the cover of the books. ✅

##### Tasks

- Implement a Read function for the books on the webpage, available for both superusers and regular users.

##### Conclusion

This stage successfully makes the data accessible to the general public, transforming the system into a publishable product, rather than just an internal tool.

#### 3. Locating Books in the Library

As a user, I can have a search bar for the books, so that I can locate them easily.

##### Design and Implementation

Design and Implementation
In addressing the need for efficient book search, a search bar was implemented to enhance user experience. Leveraging Django's querying capabilities, the search bar is designed to filter through various book attributes such as title, author, genre, or ISBN. The implementation embraces a responsive design, ensuring accessibility across different devices and browsers.

The search bar utilizes a dynamic search algorithm that offers real-time suggestions and can handle fuzzy matching to tolerate minor spelling mistakes. Integrated with the existing database, the search functionality fetches relevant results instantly, with optimized query performance.

The current design is functional yet basic in appearance, reflecting a focus on utility at this stage. Future iterations will explore more sophisticated styling, integrating the search bar seamlessly with the overall user interface for a more engaging and intuitive experience.

This approach ensures that users can locate their desired books effortlessly, catering to varied search needs and preferences, thus aligning with the core objective of user story 3.

##### Result and Next Steps

A functional but very basic-looking search bar was added. More style will be added in later stages.

##### Acceptance Criteria

- Users can search for books using a search bar. ✅

##### Tasks

- Implement a search bar.

##### Conclusion

This stage has successfully added a basic search functionality, enhancing the user experience in finding books within the catalog. Future iterations will refine the appearance and functionality of this feature.

### Development Process for User Stories 1-3

The development was carried out in an interconnected manner. These stories formed the essential foundation.

Here's the timeline of commits:

- **Aug 10, 2023**: Created the book database.
- **Aug 18, 2023**: Implemented the "Read" functionality.
- **Aug 19, 2023**: Improved search functionality and created a new user story template.

### Note on Future Development

The second block is planned for later. It was postponed to prioritize the core functionalities, aligning with the Agile philosophy.

### Appendix: Technical Specifications

Detailed technical specifications, such as the database schema or API documentation.

### Summary

This document provides a detailed guide to the development of the Library Management System, focusing on foundational functionalities. It sets the stage for further incremental development and serves as a valuable resource for stakeholders.
