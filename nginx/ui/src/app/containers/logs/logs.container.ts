import {Component} from '@angular/core';
import {Observable, of, throwError} from 'rxjs';
import {catchError, delay} from 'rxjs/internal/operators';
import {HttpClient} from '@angular/common/http';

@Component({
  selector: 'logs-page',
  templateUrl: './logs.container.html',
  styleUrls: ['./logs.container.css']
})
export class LogsContainer {

  logs$: Observable<string[]>;

  selected: string = null;

  constructor(readonly http: HttpClient) {

    this.logs$ = this.http.get<string[]>('/api/v1/logs')
      .pipe(
        catchError((error) => {
          alert(error.error);
          return throwError(error);
        })
      );
  }

  selectLog(log: string ) {

    this.selected = log;
  }
}
