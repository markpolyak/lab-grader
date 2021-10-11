import {Component, Input, OnDestroy} from '@angular/core';
import {BehaviorSubject, merge, Observable, of, Subject} from 'rxjs';
import {catchError, filter, map, tap} from 'rxjs/internal/operators';
import {HttpClient, HttpErrorResponse, HttpResponse, HttpResponseBase} from '@angular/common/http';

@Component({
  selector: 'log-viewer',
  templateUrl: './log-viewer.component.html',
  styleUrls: ['./log-viewer.component.css']
})
export class LogViewerComponent implements OnDestroy {

  interval$: Subject<HttpResponse<string> | HttpErrorResponse> = new Subject();
  log$: Observable<string | null>;
  error$: Observable<string | null>;
  showError$: Observable<boolean>;
  loading$: BehaviorSubject<boolean> = new BehaviorSubject<boolean>(false);
  file$: BehaviorSubject<string> = new BehaviorSubject<string>(null);
  intervalId: number;

  @Input()
  period: number = 200;

  @Input()
  set file(file: string) {

    this.file$.next(file);
    if (!!this.intervalId) {
      clearInterval(this.intervalId);
    }

    if (!!file) {
      this.loading$.next(true);
      this.intervalId = setInterval(() =>
          this.http.get(`/api/v1/logs/${file}`, {observe: 'response', responseType: 'text'})
            .pipe(
              filter(() => !!file),
              catchError((error: HttpErrorResponse) => of(error))
            )
            .subscribe((response) => {
              this.interval$.next(response);
              this.loading$.next(false);
            }),
        this.period
      );
    }
  }

  constructor(readonly http: HttpClient) {

    const requestInterval$: Observable<HttpErrorResponse | HttpResponse<string>> = this.interval$.pipe(
      filter((): boolean => !!this.file$.value),
    );

    this.showError$ = requestInterval$.pipe(map((response: HttpResponseBase): boolean => !response.ok));
    this.log$ = requestInterval$.pipe(
      filter((response: HttpResponseBase): boolean => response.ok),
      map((response: any): HttpResponse<string> => response),
      map((response: HttpResponse<string>): string | null => response.body)
    );
    this.error$ = requestInterval$.pipe(
      filter((response: HttpResponseBase): boolean => !response.ok),
      map((response: any): HttpErrorResponse => response),
      map((response: HttpErrorResponse): string | null => response.message)
    );
  }

  ngOnDestroy(): void {

    clearInterval(this.intervalId);
  }
}
